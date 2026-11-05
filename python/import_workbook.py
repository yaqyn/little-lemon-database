"""Read the supplied XLSX without altering it; import its actual source rows.

The standard-library XML reader preserves numeric source text before Decimal
normalization. No generated customers, orders, prices, or dates are substituted.
"""
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import posixpath
import re
from zipfile import ZipFile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "data" / "source" / "LittleLemon_data.xlsx"
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
EXPECTED_HEADERS = (
    "Row Number", "Order ID", "Order Date", "Delivery Date", "Customer ID", "Customer Name",
    "City", "Country", "Postal Code", "Country Code", " Cost", "Sales", "Quantity", "Discount",
    "Delivery Cost", "Course Name", "Cuisine Name", "Starter Name", "Desert Name", "Drink", "Sides",
)
MONEY_QUANTUM = Decimal("0.0001")


def _column_index(reference):
    result = 0
    for letter in re.match(r"[A-Z]+", reference)[0]:
        result = result * 26 + ord(letter) - ord("A") + 1
    return result - 1


def read_workbook(path=SOURCE_PATH):
    """Return workbook sheets, raw cell values/types, and Excel date-system flag."""
    path = Path(path)
    with ZipFile(path) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ["".join(node.text or "" for node in item.iter(f"{{{NS['s']}}}t"))
                       for item in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in relationships}
        properties = workbook.find("s:workbookPr", NS)
        date1904 = properties is not None and properties.attrib.get("date1904") in ("1", "true")
        sheets = []
        for sheet in workbook.find("s:sheets", NS):
            target = targets[sheet.attrib[f"{{{REL_NS}}}id"]]
            member = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
            tree = ET.fromstring(archive.read(member))
            dimension = tree.find("s:dimension", NS)
            records, types, formulas = [], [], 0
            for row in tree.find("s:sheetData", NS):
                cells, cell_types = {}, {}
                for cell in row:
                    index = _column_index(cell.attrib["r"])
                    value_node = cell.find("s:v", NS)
                    value = value_node.text if value_node is not None else None
                    kind = cell.attrib.get("t", "n")
                    if kind == "s" and value is not None:
                        value = strings[int(value)]
                    elif kind == "inlineStr":
                        value = "".join(node.text or "" for node in cell.iter(f"{{{NS['s']}}}t"))
                    formulas += cell.find("s:f", NS) is not None
                    cells[index], cell_types[index] = value, kind
                width = max(cells, default=-1) + 1
                records.append(tuple(cells.get(index) for index in range(width)))
                types.append(tuple(cell_types.get(index, "blank") for index in range(width)))
            sheets.append({"name": sheet.attrib["name"], "dimension": dimension.attrib.get("ref") if dimension is not None else None,
                           "rows": records, "cell_types": types, "formula_cells": formulas})
    return {"sheets": sheets, "date1904": date1904}


def excel_date(value, date1904=False):
    serial = Decimal(value)
    if serial != serial.to_integral_value():
        raise ValueError("An order/delivery date contains a fractional Excel date; inspect source.")
    epoch = date(1904, 1, 1) if date1904 else date(1899, 12, 30)
    return epoch + timedelta(days=int(serial))


def money(value):
    """Keep genuine half-cent sales, remove only sub-0.0001 serialization noise."""
    return Decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def source_records(path=SOURCE_PATH):
    workbook = read_workbook(path)
    sheets = [sheet for sheet in workbook["sheets"] if sheet["name"] == "Orders"]
    if len(sheets) != 1 or tuple(sheets[0]["rows"][0]) != EXPECTED_HEADERS:
        raise ValueError("Workbook Orders headers differ from the audited source; stop and review mapping.")
    rows = sheets[0]["rows"][1:]
    if any(len(row) != len(EXPECTED_HEADERS) or any(value is None or value == "" for value in row) for row in rows):
        raise ValueError("Workbook has missing cells or an unexpected row width; no data imported.")
    result = []
    for row in rows:
        result.append({
            "SourceRowNumber": int(row[0]), "SourceOrderID": row[1],
            "OrderDate": excel_date(row[2], workbook["date1904"]),
            "DeliveryDate": excel_date(row[3], workbook["date1904"]),
            "CustomerID": row[4], "CustomerName": row[5], "City": row[6],
            "Country": row[7], "PostalCodeRaw": row[8], "CountryCode": row[9],
            "Cost": money(row[10]), "Sales": money(row[11]), "Quantity": int(row[12]),
            "Discount": money(row[13]), "DeliveryCost": money(row[14]),
            "CourseName": row[15], "CuisineName": row[16], "StarterName": row[17],
            "DessertName": row[18], "DrinkName": row[19], "SidesName": row[20],
        })
    if len({row["SourceRowNumber"] for row in result}) != len(result):
        raise ValueError("Source Row Number is not unique; no data imported.")
    return result


def profile_workbook(path=SOURCE_PATH):
    path = Path(path)
    workbook = read_workbook(path)
    orders = next(sheet for sheet in workbook["sheets"] if sheet["name"] == "Orders")
    headers, rows = orders["rows"][0], orders["rows"][1:]
    row_types = orders["cell_types"][1:]
    records = source_records(path)
    column_profiles = []
    for index, header in enumerate(headers):
        values = [row[index] if index < len(row) else None for row in rows]
        kinds = Counter(row[index] if index < len(row) else "blank" for row in row_types)
        column_profiles.append({"source_name": header, "normalized_header": header.strip(),
            "missing_values": sum(value is None or value == "" for value in values),
            "unique_values": len(set(values)), "xlsx_cell_types": dict(kinds)})
    groups = defaultdict(list)
    for row in rows:
        groups[row[1]].append(row)
    varying = {header: sum(len({row[index] for row in group}) > 1 for group in groups.values())
               for index, header in enumerate(headers)}
    financial = {}
    for field, index in (("Cost",10),("Sales",11),("Discount",13),("DeliveryCost",14)):
        raw = [Decimal(row[index]) for row in rows]
        normalized = [money(row[index]) for row in rows]
        financial[field] = {"minimum": str(min(normalized)), "maximum": str(max(normalized)),
            "source_xml_sum": str(sum(raw)), "normalized_four_decimal_sum": str(sum(normalized)),
            "sum_if_each_row_rounded_to_cents": str(sum(v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) for v in raw)),
            "values_with_genuine_fractional_cents": sum(value % Decimal("0.01") != 0 for value in normalized)}
    profile = {"source_file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_size_bytes": path.stat().st_size, "date_system": "1904" if workbook["date1904"] else "1900",
        "sheet_names": [sheet["name"] for sheet in workbook["sheets"]],
        "sheets": [{"name":sheet["name"],"dimension":sheet["dimension"],"record_count":len(sheet["rows"])-1,
                    "column_count":len(sheet["rows"][0]),"formula_cells":sheet["formula_cells"]} for sheet in workbook["sheets"]],
        "columns": column_profiles, "record_count": len(rows), "exact_duplicate_rows": len(rows)-len(set(rows)),
        "distinct_source_order_ids":len(groups), "source_order_id_multiplicities":dict(Counter(len(group) for group in groups.values())),
        "source_order_ids_with_conflicting_rows":sum(len(set(group))>1 for group in groups.values()),
        "columns_varying_within_source_order_id":varying,
        "distinct_customers":len({row["CustomerID"] for row in records}),
        "distinct_menu_bundles":len({tuple(row[field] for field in ("CourseName","CuisineName","StarterName","DessertName","DrinkName","SidesName")) for row in records}),
        "delivery_before_order_count":sum(row["DeliveryDate"]<row["OrderDate"] for row in records),
        "negative_numeric_postal_codes":sum(row["PostalCodeRaw"].startswith("-") for row in records),
        "order_date_range":[str(min(row["OrderDate"] for row in records)),str(max(row["OrderDate"] for row in records))],
        "delivery_date_range":[str(min(row["DeliveryDate"] for row in records)),str(max(row["DeliveryDate"] for row in records))],
        "maximum_quantity":max(row["Quantity"] for row in records), "total_quantity":sum(row["Quantity"] for row in records),
        "financial_fields":financial,
        "transformations":["Strip leading whitespace from Cost header only.","Map source Desert Name spelling to internal DessertName without changing values.","Convert workbook date serials with its declared 1900 date system.","Preserve all 21,000 source rows and nonunique source order IDs; use SourceRowNumber for row identity.","Preserve PostalCodeRaw as text, including negative/fractional values; no invented valid postal codes.","Quantize financial values to four decimal places using Decimal ROUND_HALF_UP, preserving genuine half cents; retain original workbook unmodified.","Preserve delivery-before-order dates and flag them for analysis; do not invent corrected dates."]}
    return profile


def write_workbook_audit(path=SOURCE_PATH):
    profile = profile_workbook(path)
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "workbook_profile.json").write_text(json.dumps(profile, indent=2) + "\n")
    return profile

# Column order is explicit so database comparisons and parameter bindings agree.
TABLE_COLUMNS = {
    "Customers": ("CustomerID", "CustomerName", "City", "Country", "CountryCode"),
    "MenuItems": ("ItemID", "ItemName", "ItemType"),
    "Menus": ("MenuID", "CuisineName", "BundleKey"),
    "MenuComponents": ("MenuID", "ComponentRole", "ItemID"),
    "Orders": ("OrderID", "SourceOrderID", "CustomerID", "MenuID", "OrderDate", "PostalCodeRaw", "Cost", "Sales", "Quantity", "Discount", "DeliveryCost"),
    "OrderDeliveryStatus": ("OrderID", "DeliveryDate"),
}
KEY_COLUMNS = {table: (0,) for table in TABLE_COLUMNS}
KEY_COLUMNS["MenuComponents"] = (0, 1)
ROLE_FIELDS = (("Course", "CourseName"), ("Starter", "StarterName"), ("Dessert", "DessertName"), ("Drink", "DrinkName"), ("Side", "SidesName"))


def _bundle(row):
    return tuple(row[field] for field in ("CuisineName", "CourseName", "StarterName", "DessertName", "DrinkName", "SidesName"))


def normalized_rows(path=SOURCE_PATH):
    """Normalize source records without inventing per-component prices or quantities."""
    records = source_records(path)
    customers = {}
    for row in records:
        value = tuple(row[field] for field in TABLE_COLUMNS["Customers"])
        previous = customers.setdefault(row["CustomerID"], value)
        if previous != value:
            raise ValueError(f"Conflicting source customer attributes for {row['CustomerID']}; review source before importing.")
    item_pairs = sorted({(role, row[field]) for row in records for role, field in ROLE_FIELDS})
    item_ids = {pair: number for number, pair in enumerate(item_pairs, 1)}
    bundles = sorted({_bundle(row) for row in records})
    menu_ids = {bundle: number for number, bundle in enumerate(bundles, 1)}
    result = {
        "Customers": [customers[key] for key in sorted(customers)],
        "MenuItems": [(item_ids[pair], pair[1], pair[0]) for pair in item_pairs],
        "Menus": [(menu_ids[bundle], bundle[0], hashlib.sha256(json.dumps(bundle, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()) for bundle in bundles],
        "MenuComponents": [(menu_ids[bundle], role, item_ids[(role, bundle[index])])
                           for bundle in bundles for index, (role, _) in enumerate(ROLE_FIELDS, 1)],
        "Orders": [(row["SourceRowNumber"], row["SourceOrderID"], row["CustomerID"], menu_ids[_bundle(row)],
                    row["OrderDate"], row["PostalCodeRaw"], row["Cost"], row["Sales"], row["Quantity"],
                    row["Discount"], row["DeliveryCost"]) for row in records],
        "OrderDeliveryStatus": [(row["SourceRowNumber"], row["DeliveryDate"]) for row in records],
    }
    return result


def import_workbook(pool, path=SOURCE_PATH):
    """Insert missing source identities atomically; refuse conflicting existing rows.

    Unrelated rows are preserved. A source row or dimension key already present
    with different values is a conflict, never an instruction to overwrite it.
    """
    from python.database import pooled_cursor
    path = Path(path)
    tables = normalized_rows(path)
    inserted, totals = {}, {}
    print("Importing actual workbook records into little_lemon_database...")
    with pooled_cursor(pool) as (connection, cursor):
        try:
            for table, incoming in tables.items():
                columns = TABLE_COLUMNS[table]
                names = ", ".join(f"`{name}`" for name in columns)
                cursor.execute(f"SELECT {names} FROM `{table}`")
                key_indexes = KEY_COLUMNS[table]
                existing = {tuple(row[index] for index in key_indexes): tuple(row) for row in cursor.fetchall()}
                missing = []
                for row in incoming:
                    key = tuple(row[index] for index in key_indexes)
                    if key in existing:
                        if existing[key] != tuple(row):
                            raise ValueError(f"Import conflict in {table} at key {key}; existing records were not overwritten.")
                    else:
                        missing.append(row)
                placeholders = ", ".join("%s" for _ in columns)
                statement = f"INSERT INTO `{table}` ({names}) VALUES ({placeholders})"
                for offset in range(0, len(missing), 1000):
                    cursor.executemany(statement, missing[offset:offset + 1000])
                inserted[table] = len(missing)
                cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
                totals[table] = cursor.fetchone()[0]
            connection.commit()
            print("Workbook records committed successfully.")
        except Exception:
            connection.rollback()
            raise
    result = {"source_record_count": len(tables["Orders"]), "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "inserted_counts": inserted, "row_counts": totals}
    print("Imported source rows:", result["source_record_count"])
    print("New records inserted:", inserted)
    return result


def write_expected_manifest(path=SOURCE_PATH):
    profile = profile_workbook(path)
    tables = normalized_rows(path)
    records = source_records(path)
    manifest = {
        "source_file": "data/source/LittleLemon_data.xlsx", "source_sha256": profile["sha256"],
        "source_rows": profile["record_count"], "distinct_source_order_ids": profile["distinct_source_order_ids"],
        "table_counts": {table:len(rows) for table, rows in tables.items()},
        "max_quantity":profile["maximum_quantity"], "total_quantity":profile["total_quantity"],
        "source_sales_sum":profile["financial_fields"]["Sales"]["normalized_four_decimal_sum"],
        "source_cost_sum":profile["financial_fields"]["Cost"]["normalized_four_decimal_sum"],
        "source_discount_sum":profile["financial_fields"]["Discount"]["normalized_four_decimal_sum"],
        "source_delivery_cost_sum":profile["financial_fields"]["DeliveryCost"]["normalized_four_decimal_sum"],
        "delivery_before_order_count":profile["delivery_before_order_count"],
        "order_date_range":profile["order_date_range"], "delivery_date_range":profile["delivery_date_range"],
        "seed_customer_ids":sorted({row["CustomerID"] for row in records})[:4],
        "currency":"Not specified in supplied workbook; no currency is invented.",
        "identity_note":"Orders.OrderID is the unique source Row Number; SourceOrderID preserves the original nonunique Order ID. All 21,000 workbook rows are retained.",
    }
    (ROOT / "data" / "workbook_expected.json").write_text(json.dumps(manifest,indent=2)+"\n")
    return manifest


if __name__ == "__main__":
    print(json.dumps(write_workbook_audit(), indent=2))
    write_expected_manifest()
