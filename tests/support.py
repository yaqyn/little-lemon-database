"""Shared fixtures restricted to the assignment's dedicated database."""
from datetime import date, timedelta
from functools import lru_cache
import json
import os
from pathlib import Path
import secrets
import unittest

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = {**dotenv_values(ROOT / '.env'), **os.environ}
CONFIGURED = bool(SETTINGS.get('MYSQL_USER')) and bool(SETTINGS.get('MYSQL_PASSWORD'))
NOT_VERIFIED = 'NOT VERIFIED: configure MYSQL_USER and MYSQL_PASSWORD for actual MySQL tests.'
_POOL = None


@lru_cache(maxsize=1)
def expected():
    return json.loads((ROOT / 'data' / 'workbook_expected.json').read_text())


@lru_cache(maxsize=1)
def source_rows():
    from python.import_workbook import source_records
    return source_records()


@unittest.skipUnless(CONFIGURED, NOT_VERIFIED)
class MySQLCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global _POOL
        if _POOL is None:
            from python.database import create_pool, initialize_database, seed_bookings, create_procedures
            from python.import_workbook import import_workbook
            _POOL = create_pool()
            initialize_database(_POOL)
            import_workbook(_POOL)
            seed_bookings(_POOL)
            create_procedures(_POOL)
        cls.pool = _POOL

    def query(self, sql, params=()):
        from python.database import pooled_cursor
        with pooled_cursor(self.pool) as (_, cursor):
            cursor.execute(sql, params)
            return cursor.fetchall()

    def new_booking(self):
        customer = self.query('SELECT CustomerID FROM Customers ORDER BY CustomerID LIMIT 1')[0][0]
        while True:
            booking_id = 900_000_000 + secrets.randbelow(100_000_000)
            day = date(2040, 1, 1) + timedelta(days=secrets.randbelow(8_000))
            rows = self.query(
                'SELECT BookingID FROM Bookings WHERE BookingID=%s OR '
                '(TableNo=49 AND BookingDate IN (%s,%s))',
                (booking_id, day, day + timedelta(days=1)),
            )
            if not rows:
                self.addCleanup(self.remove_booking, booking_id)
                return booking_id, customer, day, 49

    def remove_booking(self, booking_id):
        from python.database import pooled_cursor
        with pooled_cursor(self.pool) as (connection, cursor):
            cursor.execute('DELETE FROM Bookings WHERE BookingID=%s', (booking_id,))
            connection.commit()
