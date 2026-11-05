"""The supplied workbook, its provenance, and non-destructive transformations."""
from collections import Counter
from decimal import Decimal
import hashlib
import unittest

from python.import_workbook import SOURCE_PATH, money, profile_workbook
from tests.support import expected, source_rows


class WorkbookTests(unittest.TestCase):
    def test_original_workbook_hash_is_preserved(self):
        self.assertEqual(hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest(), expected()['source_sha256'])

    def test_all_source_rows_and_repeated_identifiers_are_retained(self):
        rows = source_rows()
        self.assertEqual(len(rows), 21000)
        self.assertEqual(len({row['SourceRowNumber'] for row in rows}), 21000)
        counts = Counter(row['SourceOrderID'] for row in rows)
        self.assertEqual(len(counts), 1000)
        self.assertEqual(set(counts.values()), {21})

    def test_missing_values_and_original_column_names_are_audited(self):
        profile = profile_workbook()
        self.assertEqual(profile['sheet_names'], ['Orders'])
        self.assertEqual(profile['record_count'], 21000)
        self.assertEqual(len(profile['columns']), 21)
        self.assertEqual(sum(column['missing_values'] for column in profile['columns']), 0)
        self.assertIn(' Cost', [column['source_name'] for column in profile['columns']])
        self.assertIn('Desert Name', [column['source_name'] for column in profile['columns']])

    def test_financial_normalization_retains_genuine_half_cents(self):
        self.assertEqual(money('187.50499999999999'), Decimal('187.5050'))
        self.assertEqual(sum(row['Sales'] for row in source_rows()), Decimal('4631847.0300'))
        self.assertEqual(sum(row['Sales'] % Decimal('.01') != 0 for row in source_rows()), 5726)

    def test_delivery_date_anomalies_are_preserved_not_corrected(self):
        rows = source_rows()
        self.assertEqual(sum(row['DeliveryDate'] < row['OrderDate'] for row in rows), 9366)
        self.assertEqual(max(row['Quantity'] for row in rows), 3)
        self.assertEqual(sum(row['Quantity'] for row in rows), 44625)

    def test_dirty_postal_codes_are_kept_as_source_text(self):
        rows = source_rows()
        self.assertTrue(all(isinstance(row['PostalCodeRaw'], str) for row in rows))
        self.assertEqual(sum(row['PostalCodeRaw'].startswith('-') for row in rows), 3701)
