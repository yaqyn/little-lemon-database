"""Deploy with --setup, then validate the actual workbook-backed database."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from python.database import ROOT,create_pool,initialize_database,seed_bookings,create_procedures,pooled_cursor
from python.import_workbook import import_workbook


def setup_database(pool):
    initialize_database(pool)
    import_result=import_workbook(pool)
    seed_bookings(pool)
    create_procedures(pool)
    return import_result


def verify_database(pool):
    from decimal import Decimal
    expected=json.loads((ROOT/'data/workbook_expected.json').read_text())
    with pooled_cursor(pool,dictionary=True) as (_,cursor):
        cursor.execute('SELECT DATABASE() AS DatabaseName,VERSION() AS ServerVersion')
        server=cursor.fetchone()
        counts={}
        for table,count in expected['table_counts'].items():
            cursor.execute(f'SELECT COUNT(*) AS n FROM `{table}`')
            counts[table]=cursor.fetchone()['n']
            if counts[table]!=count:raise AssertionError(f'{table} differs from the audited workbook baseline.')
        cursor.execute('SELECT COUNT(*) AS n FROM Bookings');counts['Bookings']=cursor.fetchone()['n']
        cursor.execute('SELECT COUNT(*) AS WorkbookRecords,COUNT(DISTINCT SourceOrderID) AS DistinctSourceOrderIDs,MAX(Quantity) AS MaxQuantity,SUM(Quantity) AS TotalQuantity,SUM(Sales) AS SalesMeasureTotal,SUM(Cost) AS CostMeasureTotal,SUM(Discount) AS DiscountMeasureTotal,SUM(DeliveryCost) AS DeliveryCostMeasureTotal FROM Orders')
        summary=cursor.fetchone()
        assert summary['WorkbookRecords']==expected['source_rows']
        assert summary['DistinctSourceOrderIDs']==expected['distinct_source_order_ids']
        assert summary['MaxQuantity']==expected['max_quantity']
        assert summary['TotalQuantity']==expected['total_quantity']
        for field,key in [('SalesMeasureTotal','source_sales_sum'),('CostMeasureTotal','source_cost_sum'),('DiscountMeasureTotal','source_discount_sum'),('DeliveryCostMeasureTotal','source_delivery_cost_sum')]:
            assert summary[field]==Decimal(expected[key]),field
        cursor.execute('SELECT COUNT(*) AS n FROM Orders o JOIN OrderDeliveryStatus d ON o.OrderID=d.OrderID WHERE d.DeliveryDate<o.OrderDate')
        anomalies=cursor.fetchone()['n']
        assert anomalies==expected['delivery_before_order_count']
        cursor.execute('SELECT ROUTINE_NAME FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=DATABASE() ORDER BY ROUTINE_NAME')
        procedures=[row['ROUTINE_NAME'] for row in cursor.fetchall()]
        assert set(procedures)=={'GetMaxQuantity','ManageBooking','UpdateBooking','AddBooking','CancelBooking'}
    result={**server,'row_counts':counts,'summary':summary,'delivery_before_order_count':anomalies,'procedures':procedures}
    print(json.dumps(result,indent=2,default=str))
    print('Actual workbook records, constraints and procedure availability verified.')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--setup',action='store_true',help='Safely create/import missing assignment records first.')
    args=parser.parse_args()
    pool=create_pool()
    if args.setup:setup_database(pool)
    verify_database(pool)
