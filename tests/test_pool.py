"""Pool safety, schema isolation, error reporting and real checkout semantics."""
from contextlib import redirect_stdout
from io import StringIO
import unittest
from unittest.mock import MagicMock, patch

from mysql.connector import Error
from mysql.connector.errors import PoolError

from python.database import create_pool, pooled_cursor
from tests.support import MySQLCase


class PoolUnitTests(unittest.TestCase):
    def pool_fixture(self):
        pool = MagicMock()
        connection = pool.get_connection.return_value
        cursor = connection.cursor.return_value
        return pool, connection, cursor

    def test_cursor_and_connection_are_closed_on_success(self):
        pool, connection, cursor = self.pool_fixture()
        with pooled_cursor(pool) as (active_connection, active_cursor):
            self.assertIs(active_connection, connection)
            self.assertIs(active_cursor, cursor)
        cursor.close.assert_called_once()
        connection.close.assert_called_once()
        connection.cmd_init_db.assert_called_once_with('little_lemon_database')

    def test_sql_error_rolls_back_and_returns_connection(self):
        pool, connection, cursor = self.pool_fixture()
        cursor.execute.side_effect = Error(msg='Intentional test failure', errno=1054)
        output = StringIO()
        with redirect_stdout(output), self.assertRaises(Error):
            with pooled_cursor(pool) as (_, active_cursor):
                active_cursor.execute('test statement')
        connection.rollback.assert_called()
        cursor.close.assert_called_once()
        connection.close.assert_called_once()
        self.assertIn('1054', output.getvalue())
        self.assertIn('Intentional test failure', output.getvalue())

    def test_python_error_also_rolls_back_and_returns_connection(self):
        pool, connection, cursor = self.pool_fixture()
        with self.assertRaisesRegex(ValueError, 'fixture'):
            with pooled_cursor(pool):
                raise ValueError('fixture')
        connection.rollback.assert_called()
        cursor.close.assert_called_once()
        connection.close.assert_called_once()

    def test_cursor_creation_failure_returns_connection(self):
        pool, connection, _ = self.pool_fixture()
        connection.cursor.side_effect = Error(msg='Cursor test failure', errno=2000)
        with self.assertRaises(Error):
            with pooled_cursor(pool):
                self.fail('Context must not yield a missing cursor.')
        connection.close.assert_called_once()

    def test_cursor_close_failure_still_returns_connection(self):
        pool, connection, cursor = self.pool_fixture()
        cursor.close.side_effect = Error(msg='Close test failure', errno=2000)
        with self.assertRaises(Error):
            with pooled_cursor(pool):
                pass
        connection.close.assert_called_once()

    def test_exhausted_pool_propagates_error_without_a_lease(self):
        pool = MagicMock()
        pool.get_connection.side_effect = PoolError(msg='Exhausted test pool')
        with self.assertRaises(PoolError):
            with pooled_cursor(pool):
                self.fail('An exhausted pool must not yield.')
        pool.get_connection.assert_called_once()

    def test_other_little_lemon_databases_are_rejected(self):
        for database in ['littlelemon', 'little_lemon_sales']:
            with self.subTest(database=database), patch('python.database.MySQLConnectionPool') as constructor:
                with self.assertRaises(ValueError):
                    create_pool({'host': '127.0.0.1', 'user': 'fixture',
                                 'password': 'fixture-only', 'database': database})
                constructor.assert_not_called()

    def test_failed_pool_creation_does_not_print_success_or_password(self):
        config = {'host': '127.0.0.1', 'user': 'fixture',
                  'password': 'fixture-secret-not-output', 'database': 'little_lemon_database'}
        output = StringIO()
        with patch('python.database.MySQLConnectionPool', side_effect=Error(msg='Denied fixture', errno=1045)):
            with redirect_stdout(output), self.assertRaises(Error):
                create_pool(config)
        self.assertIn('1045', output.getvalue())
        self.assertIn('Denied fixture', output.getvalue())
        self.assertNotIn('Connection established successfully.', output.getvalue())
        self.assertNotIn(config['password'], output.getvalue())

    def test_bootstrap_pool_omits_default_schema(self):
        with patch('python.database.MySQLConnectionPool') as constructor:
            constructor.return_value.pool_name = 'little_lemon_database_pool'
            constructor.return_value.pool_size = 2
            with redirect_stdout(StringIO()):
                create_pool({'host': '127.0.0.1', 'user': 'fixture', 'password': 'fixture-only',
                             'database': 'little_lemon_database'})
            self.assertEqual(constructor.call_args.kwargs['pool_size'], 2)
            self.assertNotIn('database', constructor.call_args.kwargs)


class PoolIntegrationTests(MySQLCase):
    def test_connection_selects_only_assignment_database(self):
        database, version = self.query('SELECT DATABASE(), VERSION()')[0]
        self.assertEqual(database, 'little_lemon_database')
        self.assertGreaterEqual(int(version.split('.')[0]), 8)

    def test_two_slots_can_be_returned_and_reacquired(self):
        first = second = replacement = None
        try:
            first = self.pool.get_connection()
            second = self.pool.get_connection()
            with self.assertRaises(PoolError):
                self.pool.get_connection()
            first.close()
            first = None
            replacement = self.pool.get_connection()
            self.assertTrue(replacement.is_connected())
        finally:
            for connection in (first, second, replacement):
                if connection is not None:
                    connection.close()

    def test_real_sql_failure_does_not_exhaust_the_pool(self):
        with self.assertRaises(Error):
            with pooled_cursor(self.pool) as (_, cursor):
                cursor.execute('SELECT DeliberatelyMissingColumn FROM Customers')
        first = second = None
        try:
            first = self.pool.get_connection()
            second = self.pool.get_connection()
            self.assertTrue(first.is_connected() and second.is_connected())
        finally:
            for connection in (first, second):
                if connection is not None:
                    connection.close()
