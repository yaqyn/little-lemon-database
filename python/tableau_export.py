"""Export verified one-row-per-source-record data without component-join fan-out."""
import csv
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from python.database import ROOT,create_pool,pooled_cursor

FACT_SQL="""WITH bundle AS (
    SELECT mc.MenuID,
      MAX(CASE WHEN mc.ComponentRole='Course' THEN mi.ItemName END) AS CourseName,
      MAX(CASE WHEN mc.ComponentRole='Starter' THEN mi.ItemName END) AS StarterName,
      MAX(CASE WHEN mc.ComponentRole='Dessert' THEN mi.ItemName END) AS DessertName,
      MAX(CASE WHEN mc.ComponentRole='Drink' THEN mi.ItemName END) AS DrinkName,
      MAX(CASE WHEN mc.ComponentRole='Side' THEN mi.ItemName END) AS SideName
    FROM MenuComponents mc JOIN MenuItems mi ON mi.ItemID=mc.ItemID
    GROUP BY mc.MenuID
) SELECT o.OrderID AS OrderRecordID,o.SourceOrderID,o.CustomerID,c.CustomerName,c.City,c.Country,c.CountryCode,
    o.OrderDate,d.DeliveryDate,o.PostalCodeRaw,m.CuisineName,
    b.CourseName,b.StarterName,b.DessertName,b.DrinkName,b.SideName,
    o.Quantity,o.Cost,o.Sales,o.Discount,o.DeliveryCost,
    (d.DeliveryDate<o.OrderDate) AS DeliveryBeforeOrder
FROM Orders o JOIN Customers c ON c.CustomerID=o.CustomerID
JOIN Menus m ON m.MenuID=o.MenuID JOIN bundle b ON b.MenuID=o.MenuID
JOIN OrderDeliveryStatus d ON d.OrderID=o.OrderID ORDER BY o.OrderID"""

EXPORT_QUERIES={
    'order_facts.csv':FACT_SQL,
    'bookings.csv':"SELECT b.BookingID,b.CustomerID,c.CustomerName,b.BookingDate,b.TableNo,IF(b.BookingID BETWEEN 1 AND 4,'Supplemental demo booking fixture','Additional booking') AS DataOrigin FROM Bookings b JOIN Customers c ON b.CustomerID=c.CustomerID ORDER BY b.BookingID",
    'menu_components.csv':"SELECT m.MenuID,m.CuisineName,mc.ComponentRole,mi.ItemID,mi.ItemName FROM Menus m JOIN MenuComponents mc ON m.MenuID=mc.MenuID JOIN MenuItems mi ON mi.ItemID=mc.ItemID ORDER BY m.MenuID,mc.ComponentRole",
    'sales_by_month.csv':"SELECT DATE_FORMAT(OrderDate,'%Y-%m') AS OrderMonth,COUNT(*) AS WorkbookRecords,SUM(Sales) AS SalesMeasureTotal,SUM(Quantity) AS QuantityTotal FROM Orders GROUP BY DATE_FORMAT(OrderDate,'%Y-%m') ORDER BY OrderMonth",
    'sales_by_cuisine.csv':"SELECT m.CuisineName,COUNT(*) AS WorkbookRecords,SUM(o.Sales) AS SalesMeasureTotal,SUM(o.Quantity) AS QuantityTotal FROM Orders o JOIN Menus m ON o.MenuID=m.MenuID GROUP BY m.CuisineName ORDER BY SalesMeasureTotal DESC",
}


def export_tableau_data(pool):
    directory=ROOT/'tableau';directory.mkdir(exist_ok=True)
    expected=json.loads((ROOT/'data/workbook_expected.json').read_text())
    manifest={}
    with pooled_cursor(pool,dictionary=True) as (_,cursor):
        for filename,sql in EXPORT_QUERIES.items():
            cursor.execute(sql);rows=cursor.fetchall()
            if filename=='order_facts.csv':
                assert len(rows)==expected['source_rows']
                assert len({r['OrderRecordID'] for r in rows})==len(rows)
                from decimal import Decimal
                assert sum(r['Sales'] for r in rows)==Decimal(expected['source_sales_sum'])
                assert sum(r['DeliveryBeforeOrder'] for r in rows)==expected['delivery_before_order_count']
            path=directory/filename
            fields=[item[0] for item in cursor.description]
            with path.open('w',newline='',encoding='utf-8') as stream:
                writer=csv.DictWriter(stream,fieldnames=fields)
                writer.writeheader();writer.writerows(rows)
            manifest[filename]={'rows':len(rows),'columns':fields,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest['provenance']={'source':'data/source/LittleLemon_data.xlsx','source_sha256':expected['source_sha256'],'grain':'order_facts has exactly one row per workbook Row Number, not one row per distinct source Order ID.','currency':'Not supplied; chart axes must use source units, not an invented currency.','tableau_execution':'NOT VERIFIED: Tableau Desktop is not accessible. CSV exports are actual verified database outputs.'}
    (directory/'export_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Verified Tableau-ready exports:',{k:v['rows'] for k,v in manifest.items() if isinstance(v,dict) and 'rows' in v})
    return manifest


if __name__=='__main__':export_tableau_data(create_pool())
