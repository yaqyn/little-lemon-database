"""Tableau-ready outputs are actual, one-row-per-source-record database extracts."""
import csv
from decimal import Decimal
import hashlib
from python.tableau_export import export_tableau_data
from tests.support import MySQLCase,ROOT,expected

class TableauExportTests(MySQLCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manifest=export_tableau_data(cls.pool)

    def test_fact_export_preserves_grain_and_source_financial_total(self):
        with (ROOT/'tableau/order_facts.csv').open(newline='',encoding='utf-8') as stream:
            rows=list(csv.DictReader(stream))
        self.assertEqual(len(rows),expected()['source_rows'])
        self.assertEqual(len({r['OrderRecordID'] for r in rows}),21000)
        self.assertEqual(len({r['SourceOrderID'] for r in rows}),1000)
        self.assertEqual(sum(Decimal(r['Sales']) for r in rows),Decimal(expected()['source_sales_sum']))
        self.assertEqual(sum(int(r['DeliveryBeforeOrder']) for r in rows),9366)

    def test_export_files_match_manifest_checksums(self):
        for name,info in self.manifest.items():
            if not name.endswith('.csv'):continue
            p=ROOT/'tableau'/name
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),info['sha256'])
            with p.open(newline='',encoding='utf-8') as stream:
                self.assertEqual(len(list(csv.DictReader(stream))),info['rows'])

    def test_booking_export_is_separate_and_labeled_demo_data(self):
        with (ROOT/'tableau/bookings.csv').open(newline='',encoding='utf-8') as stream:
            rows=list(csv.DictReader(stream))
        self.assertEqual({r['BookingID'] for r in rows},{'1','2','3','4'})
        self.assertTrue(all(r['DataOrigin']=='Supplemental demo booking fixture' for r in rows))
