"""Actual schema relationships, imports, financial reconciliation and ER alignment."""
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from mysql.connector import Error

from python.database import call_procedure, pooled_cursor, seed_bookings
from python.import_workbook import import_workbook, normalized_rows
from tests.support import MySQLCase, ROOT, expected, source_rows


class DatabaseTests(MySQLCase):
    def test_required_source_aware_tables_exist(self):
        names = {row[0] for row in self.query('SHOW TABLES')}
        self.assertEqual(names, {'Customers', 'MenuItems', 'Menus', 'MenuComponents', 'Orders',
                                 'OrderDeliveryStatus', 'Bookings'})

    def test_expected_foreign_keys_are_deployed(self):
        rows = self.query('SELECT TABLE_NAME,COLUMN_NAME,REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME '
                          'FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() '
                          'AND REFERENCED_TABLE_NAME IS NOT NULL')
        self.assertEqual(set(rows), {
            ('Bookings', 'CustomerID', 'Customers', 'CustomerID'),
            ('Orders', 'CustomerID', 'Customers', 'CustomerID'),
            ('Orders', 'MenuID', 'Menus', 'MenuID'),
            ('MenuComponents', 'MenuID', 'Menus', 'MenuID'),
            ('MenuComponents', 'ItemID', 'MenuItems', 'ItemID'),
            ('MenuComponents', 'ComponentRole', 'MenuItems', 'ItemType'),
            ('OrderDeliveryStatus', 'OrderID', 'Orders', 'OrderID'),
        })

    def test_imported_table_counts_match_the_actual_workbook(self):
        for table, count in expected()['table_counts'].items():
            with self.subTest(table=table):
                self.assertEqual(self.query(f'SELECT COUNT(*) FROM `{table}`')[0][0], count)
        self.assertEqual(self.query('SELECT COUNT(*) FROM Bookings')[0][0], 4)

    def test_import_and_booking_seed_are_safe_to_rerun(self):
        result = import_workbook(self.pool)
        self.assertTrue(all(count == 0 for count in result['inserted_counts'].values()))
        self.assertEqual(result['row_counts'], expected()['table_counts'])
        before = self.query('SELECT * FROM Bookings ORDER BY BookingID')
        seed_bookings(self.pool)
        self.assertEqual(self.query('SELECT * FROM Bookings ORDER BY BookingID'), before)

    def test_import_conflicts_preserve_existing_records(self):
        tables = normalized_rows()
        customer = tables['Customers'][0]
        altered = dict(tables)
        altered['Customers'] = [(customer[0], 'Conflicting test name', *customer[2:]), *tables['Customers'][1:]]
        before = self.query('SELECT * FROM Customers WHERE CustomerID=%s', (customer[0],))
        with patch('python.import_workbook.normalized_rows', return_value=altered):
            with self.assertRaisesRegex(ValueError, 'conflict'):
                import_workbook(self.pool)
        self.assertEqual(self.query('SELECT * FROM Customers WHERE CustomerID=%s', (customer[0],)), before)

    def test_source_order_ids_are_not_falsely_deduplicated(self):
        row_count, source_count = self.query('SELECT COUNT(*),COUNT(DISTINCT SourceOrderID) FROM Orders')[0]
        self.assertEqual((row_count, source_count), (21000, 1000))
        self.assertEqual(self.query('SELECT SourceOrderID FROM Orders GROUP BY SourceOrderID HAVING COUNT(*)<>21'), [])

    def test_actual_money_and_quantity_totals_reconcile(self):
        sales, cost, discount, delivery, quantity, max_quantity = self.query(
            'SELECT SUM(Sales),SUM(Cost),SUM(Discount),SUM(DeliveryCost),SUM(Quantity),MAX(Quantity) FROM Orders')[0]
        self.assertEqual(sales, Decimal(expected()['source_sales_sum']))
        self.assertEqual(cost, Decimal(expected()['source_cost_sum']))
        self.assertEqual(discount, Decimal(expected()['source_discount_sum']))
        self.assertEqual(delivery, Decimal(expected()['source_delivery_cost_sum']))
        self.assertEqual(quantity, 44625)
        self.assertEqual(max_quantity, 3)
        self.assertEqual(self.query('SELECT COUNT(*) FROM Orders WHERE Sales*100 <> ROUND(Sales*100)')[0][0], 5726)

    def test_delivery_anomalies_and_postal_values_match_source(self):
        count = self.query('SELECT COUNT(*) FROM Orders o JOIN OrderDeliveryStatus d ON o.OrderID=d.OrderID '
                           'WHERE d.DeliveryDate < o.OrderDate')[0][0]
        self.assertEqual(count, expected()['delivery_before_order_count'])
        sample = next(row for row in source_rows() if row['PostalCodeRaw'].startswith('-'))
        self.assertEqual(self.query('SELECT PostalCodeRaw FROM Orders WHERE OrderID=%s',
                                    (sample['SourceRowNumber'],))[0][0], sample['PostalCodeRaw'])

    def test_foreign_key_rejects_unknown_booking_customer(self):
        booking_id, _, day, table = self.new_booking()
        with self.assertRaises(Error):
            with pooled_cursor(self.pool) as (_, cursor):
                cursor.execute('INSERT INTO Bookings VALUES(%s,%s,%s,%s)',
                               (booking_id, 'customer-not-in-workbook', day, table))
        self.assertEqual(self.query('SELECT COUNT(*) FROM Bookings WHERE BookingID=%s', (booking_id,))[0][0], 0)

    def test_committed_booking_is_visible_to_another_checkout(self):
        booking_id, customer, day, table = self.new_booking()
        call_procedure(self.pool, 'AddBooking', (booking_id, customer, day, table), commit=True)
        self.assertEqual(self.query('SELECT CustomerID,BookingDate,TableNo FROM Bookings WHERE BookingID=%s',
                                    (booking_id,)), [(customer, day, table)])

    def test_error_rolls_back_prior_writes_in_same_transaction(self):
        booking_id, customer, day, table = self.new_booking()
        with self.assertRaises(Error):
            with pooled_cursor(self.pool) as (_, cursor):
                cursor.execute('INSERT INTO Bookings VALUES(%s,%s,%s,%s)', (booking_id, customer, day, table))
                cursor.execute('SELECT DeliberatelyMissingColumn FROM Customers')
        self.assertEqual(self.query('SELECT COUNT(*) FROM Bookings WHERE BookingID=%s', (booking_id,))[0][0], 0)

    def test_er_diagram_metadata_matches_deployed_schema(self):
        from scripts.generate_er import compare_schema
        self.assertTrue(compare_schema(self.pool))
        png = ROOT / 'diagrams' / 'little_lemon_er_diagram.png'
        pdf = ROOT / 'diagrams' / 'little_lemon_er_diagram.pdf'
        self.assertEqual(png.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
        self.assertTrue(pdf.read_bytes().startswith(b'%PDF-'))
