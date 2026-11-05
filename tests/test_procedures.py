"""Five exact procedure names and safe successful/unsuccessful transactions."""
from datetime import date, timedelta
from mysql.connector import Error

from python.database import call_procedure, create_procedures, pooled_cursor
from tests.support import MySQLCase


class ProcedureTests(MySQLCase):
    def test_all_five_procedures_and_baseline_signatures_exist(self):
        names = {row[0] for row in self.query('SELECT ROUTINE_NAME FROM information_schema.ROUTINES '
                                            "WHERE ROUTINE_SCHEMA=DATABASE() AND ROUTINE_TYPE='PROCEDURE'")}
        self.assertEqual(names, {'GetMaxQuantity', 'ManageBooking', 'UpdateBooking', 'AddBooking', 'CancelBooking'})
        parameters = self.query('SELECT SPECIFIC_NAME,COUNT(*) FROM information_schema.PARAMETERS '
                                'WHERE SPECIFIC_SCHEMA=DATABASE() AND PARAMETER_MODE IS NOT NULL GROUP BY SPECIFIC_NAME')
        self.assertEqual(dict(parameters), {'ManageBooking': 2, 'UpdateBooking': 2, 'AddBooking': 4, 'CancelBooking': 1})
        create_procedures(self.pool)
        self.assertEqual(call_procedure(self.pool, 'GetMaxQuantity'), [[(3,)]])

    def test_get_max_quantity_uses_imported_order_quantities(self):
        expected = self.query('SELECT MAX(Quantity) FROM Orders')[0][0]
        self.assertEqual(call_procedure(self.pool, 'GetMaxQuantity'), [[(expected,)]])
        self.assertEqual(expected, 3)

    def test_manage_booking_reports_available_and_booked_table(self):
        booking_id, customer, day, table = self.new_booking()
        available = call_procedure(self.pool, 'ManageBooking', (day, table))[0][0]
        self.assertEqual(available[1], 0)
        self.assertIn(str(table), available[0])
        self.assertIn('available', available[0].lower())
        call_procedure(self.pool, 'AddBooking', (booking_id, customer, day, table), commit=True)
        booked = call_procedure(self.pool, 'ManageBooking', (day, table))[0][0]
        self.assertEqual(booked[1], 1)
        self.assertIn('already booked', booked[0].lower())

    def test_manage_booking_rejects_invalid_inputs(self):
        for args in [(None, 1), (date(2022, 1, 1), None), (date(2022, 1, 1), 0), (date(2022, 1, 1), 51)]:
            with self.subTest(args=args), self.assertRaises(Error):
                call_procedure(self.pool, 'ManageBooking', args)

    def test_add_update_and_cancel_booking_persist(self):
        booking_id, customer, day, table = self.new_booking()
        call_procedure(self.pool, 'AddBooking', (booking_id, customer, day, table), commit=True)
        changed = day + timedelta(days=1)
        result = call_procedure(self.pool, 'UpdateBooking', (booking_id, changed), commit=True)
        self.assertEqual(result[0][0][0], booking_id)
        self.assertEqual(self.query('SELECT BookingDate FROM Bookings WHERE BookingID=%s', (booking_id,)), [(changed,)])
        result = call_procedure(self.pool, 'CancelBooking', (booking_id,), commit=True)
        self.assertEqual(result[0][0][0], booking_id)
        self.assertEqual(self.query('SELECT COUNT(*) FROM Bookings WHERE BookingID=%s', (booking_id,))[0][0], 0)

    def test_historical_course_dates_are_valid(self):
        booking_id, customer, _, table = self.new_booking()
        day = date(1998, 2, 3)
        while self.query('SELECT BookingID FROM Bookings WHERE BookingDate=%s AND TableNo=%s', (day, table)):
            day += timedelta(days=1)
        call_procedure(self.pool, 'AddBooking', (booking_id, customer, day, table), commit=True)
        self.assertEqual(self.query('SELECT BookingDate FROM Bookings WHERE BookingID=%s', (booking_id,)), [(day,)])

    def test_add_booking_invalid_values_are_rejected(self):
        booking_id, customer, day, table = self.new_booking()
        cases = [(0, customer, day, table), (booking_id, None, day, table),
                 (booking_id, '', day, table), (booking_id, 'no-such-customer', day, table),
                 (booking_id, customer, None, table), (booking_id, customer, day, 0),
                 (booking_id, customer, day, 51)]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(Error):
                call_procedure(self.pool, 'AddBooking', args, commit=True)
        self.assertEqual(self.query('SELECT COUNT(*) FROM Bookings WHERE BookingID=%s', (booking_id,))[0][0], 0)

    def test_duplicate_date_and_table_are_rejected(self):
        first, customer, day, table = self.new_booking()
        second, _, _, _ = self.new_booking()
        call_procedure(self.pool, 'AddBooking', (first, customer, day, table), commit=True)
        with self.assertRaises(Error):
            call_procedure(self.pool, 'AddBooking', (second, customer, day, table), commit=True)
        self.assertEqual(self.query('SELECT COUNT(*) FROM Bookings WHERE BookingDate=%s AND TableNo=%s', (day, table))[0][0], 1)

    def test_existing_booking_identifier_is_never_overwritten(self):
        before = self.query('SELECT * FROM Bookings ORDER BY BookingID LIMIT 1')[0]
        with self.assertRaises(Error):
            call_procedure(self.pool, 'AddBooking', (before[0], before[1], before[2] + timedelta(days=100), before[3]), commit=True)
        self.assertEqual(self.query('SELECT * FROM Bookings WHERE BookingID=%s', (before[0],))[0], before)

    def test_update_cannot_collide_with_another_booking(self):
        first, customer, day, table = self.new_booking()
        second, _, _, _ = self.new_booking()
        call_procedure(self.pool, 'AddBooking', (first, customer, day, table), commit=True)
        call_procedure(self.pool, 'AddBooking', (second, customer, day + timedelta(days=1), table), commit=True)
        with self.assertRaises(Error):
            call_procedure(self.pool, 'UpdateBooking', (first, day + timedelta(days=1)), commit=True)
        self.assertEqual(self.query('SELECT BookingDate FROM Bookings WHERE BookingID=%s', (first,)), [(day,)])

    def test_missing_booking_updates_and_cancellations_are_errors(self):
        booking_id, _, day, _ = self.new_booking()
        for name, args in [('UpdateBooking', (booking_id, day)), ('CancelBooking', (booking_id,))]:
            with self.subTest(name=name), self.assertRaises(Error):
                call_procedure(self.pool, name, args, commit=True)

    def test_null_update_and_cancel_inputs_are_rejected(self):
        for name, args in [('UpdateBooking', (None, date(2022, 1, 1))),
                           ('UpdateBooking', (0, date(2022, 1, 1))),
                           ('UpdateBooking', (1, None)), ('CancelBooking', (None,)), ('CancelBooking', (0,))]:
            with self.subTest(name=name, args=args), self.assertRaises(Error):
                call_procedure(self.pool, name, args, commit=True)

    def test_add_without_python_commit_is_rolled_back(self):
        booking_id, customer, day, table = self.new_booking()
        call_procedure(self.pool, 'AddBooking', (booking_id, customer, day, table))
        self.assertEqual(self.query('SELECT COUNT(*) FROM Bookings WHERE BookingID=%s', (booking_id,))[0][0], 0)

    def test_update_without_python_commit_preserves_original_date(self):
        booking_id, customer, day, table = self.new_booking()
        call_procedure(self.pool, 'AddBooking', (booking_id, customer, day, table), commit=True)
        call_procedure(self.pool, 'UpdateBooking', (booking_id, day + timedelta(days=1)))
        self.assertEqual(self.query('SELECT BookingDate FROM Bookings WHERE BookingID=%s', (booking_id,)), [(day,)])

    def test_cancel_without_python_commit_preserves_booking(self):
        booking_id, customer, day, table = self.new_booking()
        call_procedure(self.pool, 'AddBooking', (booking_id, customer, day, table), commit=True)
        call_procedure(self.pool, 'CancelBooking', (booking_id,))
        self.assertEqual(self.query('SELECT COUNT(*) FROM Bookings WHERE BookingID=%s', (booking_id,))[0][0], 1)
