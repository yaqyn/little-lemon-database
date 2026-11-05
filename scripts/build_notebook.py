"""Build the database assignment notebook; execute separately to capture real outputs."""
from pathlib import Path
import textwrap
import nbformat as nbf
ROOT=Path(__file__).resolve().parents[1]
nb=nbf.v4.new_notebook()
nb.metadata.kernelspec={'display_name':'Python 3','language':'python','name':'python3'}
nb.metadata.language_info={'name':'python','version':'3.14'}
cells=[]
def section(title,text,code=None):
    cells.append(nbf.v4.new_markdown_cell('## '+title+'\n\n'+text))
    if code:cells.append(nbf.v4.new_code_cell(textwrap.dedent(code).strip()))
cells.append(nbf.v4.new_markdown_cell('# Little Lemon Database\n\nA source-aware MySQL model and Python client for the supplied peer-grade brief. The workbook is retained unchanged. Booking fixtures are separately labeled demonstrations; no unavailable staff, item-price or booking-to-order data is invented.'))
section('1. Imports and private configuration','All MySQL operations use pooled Connector/Python connections. Credentials are read from a private environment file and are never printed.', '''
    from pathlib import Path
    from datetime import date, timedelta
    from decimal import Decimal
    import json, csv, secrets
    import mysql.connector
    from mysql.connector import Error
    from IPython.display import SVG, display
    from python.database import ROOT, load_config, create_pool, pooled_cursor, call_procedure
    from python.import_workbook import SOURCE_PATH, import_workbook
    from python.verify_database import setup_database, verify_database
    from python.run_procedures import demonstrate_procedures
    from python.tableau_export import export_tableau_data
    from scripts.generate_er import compare_schema
    print('Connector/Python:',mysql.connector.__version__)
    config=load_config()
    print('Dedicated database:',config['database'])
    pool=create_pool(config)
''')
section('2. Inspect the actual source workbook','The single Orders worksheet has 21 columns and 21,000 rows. Repeated source Order IDs differ in monetary and postal values, so they are preserved. Database Orders.OrderID uses the unique source Row Number; SourceOrderID retains the repeated identifier.', '''
    profile=json.loads((ROOT/'data/workbook_profile.json').read_text())
    print('Source workbook SHA256:',profile['sha256'])
    print('Sheets:',profile['sheet_names'])
    print('Rows:',profile['record_count'])
    print('Distinct source order IDs:',profile['distinct_source_order_ids'])
    for column in profile['columns']:
        print(column['source_name'],column['xlsx_cell_types'],'missing:',column['missing_values'])
''')
section('3. Deploy and import without overwriting','Create only little_lemon_database. Tables and routines use IF NOT EXISTS. Importing compares existing identities and refuses conflicts rather than overwriting them. MySQL DDL has implicit commits; the workbook import is a separate transaction. Existing rows are expected on a rerun.', '''
    import_result=setup_database(pool)
    print('Source import:',import_result)
    verification=verify_database(pool)
''')
section('4. Verify the deployed ER model','The supplied PNG and PDF are generated from live information_schema columns, keys and foreign keys. The checked manifest must match this deployment. No .mwb is claimed because MySQL Workbench is unavailable.', '''
    assert compare_schema(pool)
    print('ER metadata equals the deployed seven-table schema.')
    display(SVG(filename=str(ROOT/'diagrams/little_lemon_er_diagram.svg')))
''')
section('5. Execute all five required procedures','GetMaxQuantity returns MAX(Orders.Quantity). ManageBooking checks a date/table, UpdateBooking changes the date, AddBooking creates a row, and CancelBooking removes it. Historical dates remain valid for course-era examples. The demo changes only its own temporary booking.', '''
    procedure_demo=demonstrate_procedures(pool)
    print(procedure_demo)
''')
section('6. Retrieve results and demonstrate commits','The following cell shows callproc, stored_results and commit directly. A second pooled checkout confirms persistence. Finally, it cancels only the newly created record. The connector deprecates stored_results, but the tested pinned version still supports this requested assignment API.', '''
    with pooled_cursor(pool) as (connection,cursor):
        cursor.execute('SELECT CustomerID FROM Customers ORDER BY CustomerID LIMIT 1')
        customer_id=cursor.fetchone()[0]
        while True:
            own_id=1_300_000_000+secrets.randbelow(100_000_000)
            own_day=date.today()+timedelta(days=400+secrets.randbelow(500))
            cursor.execute('SELECT COUNT(*) FROM Bookings WHERE BookingID=%s OR (BookingDate=%s AND TableNo=47)',(own_id,own_day))
            if cursor.fetchone()[0]==0:break
    created=False
    try:
        with pooled_cursor(pool) as (connection,cursor):
            cursor.callproc('AddBooking',(own_id,customer_id,own_day,47))
            for result in cursor.stored_results():
                try:
                    for row in result.fetchall():print(row)
                finally:result.close()
            connection.commit()
            created=True
            print('Insert committed.')
        with pooled_cursor(pool) as (connection,cursor):
            cursor.execute('SELECT COUNT(*) FROM Bookings WHERE BookingID=%s',(own_id,))
            assert cursor.fetchone()[0]==1
            print('A subsequent checkout sees the committed booking.')
    finally:
        if created:call_procedure(pool,'CancelBooking',(own_id,),commit=True)
''')
section('7. Preserve and report data-quality findings','No currency is identified. The meaning of Discount is unspecified, so it is not applied as an invented percentage or subtracted again. Four decimal places preserve genuine half-cent Sales values. Delivery chronology and raw postal anomalies remain traceable.', '''
    print('Rows with delivery before order:',profile['delivery_before_order_count'])
    print('Negative raw postal values:',profile['negative_numeric_postal_codes'])
    print('Financial normalization:',json.dumps(profile['financial_fields'],indent=2))
    print('Maximum order quantity:',call_procedure(pool,'GetMaxQuantity')[0][0][0])
''')
section('8. Export Tableau-ready data without fan-out','The fact export pivots five component roles into columns before joining. It keeps one row per workbook row; joining five components directly and summing Sales would multiply results by five. Tableau Desktop is NOT VERIFIED and no native workbook is fabricated.', '''
    exports=export_tableau_data(pool)
    print('Export row counts:',{name:info['rows'] for name,info in exports.items() if isinstance(info,dict) and 'rows' in info})
    with (ROOT/'tableau/order_facts.csv').open(newline='',encoding='utf-8') as stream:
        facts=list(csv.DictReader(stream))
    assert len(facts)==21000
    assert sum(Decimal(row['Sales']) for row in facts)==Decimal('4631847.0300')
    print('Fact export sales measure total:',sum(Decimal(row['Sales']) for row in facts))
''')
section('9. Source-measure analysis preview','This Python chart is a verified preview, not a Tableau screenshot or a real-business revenue claim. It sums all preserved workbook rows, in source units. Use tableau/README.md to build and verify a genuine Tableau workbook elsewhere.', '''
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    with (ROOT/'tableau/sales_by_cuisine.csv').open(newline='',encoding='utf-8') as stream:
        cuisine=list(csv.DictReader(stream))
    fig,ax=plt.subplots(figsize=(8,4),layout='constrained')
    ax.bar([r['CuisineName'] for r in cuisine],[float(r['SalesMeasureTotal']) for r in cuisine],color='#24483e')
    ax.set(title='Workbook Sales measure by cuisine',ylabel='Sales (source units)',xlabel='Cuisine')
    ax.spines[['top','right']].set_visible(False)
    ax.ticklabel_format(axis='y',style='plain')
    path=ROOT/'output/sales_measure_by_cuisine.svg'
    path.parent.mkdir(exist_ok=True)
    fig.savefig(path,metadata={'Creator':'Abdulrahman M. Yaqyn','Date':None})
    plt.close(fig)
    display(SVG(filename=str(path)))
''')
section('10. Cleanup and repeatability','A deliberately handled SQL error must not exhaust the pool. All uncommitted writes roll back on cleanup, every cursor closes, and every checkout returns to the pool. Physical pooled sockets are reused until the kernel exits.', '''
    from contextlib import ExitStack
    try:
        with pooled_cursor(pool) as (connection,cursor):cursor.execute('SELECT DeliberatelyMissingColumn FROM Customers')
    except Error as er:
        print('Expected error handled:',er.errno,er.msg)
    with ExitStack() as stack:
        for number in range(pool.pool_size):
            connection,cursor=stack.enter_context(pooled_cursor(pool))
            cursor.execute('SELECT 1');assert cursor.fetchone()[0]==1
            print('Reusable pool slot:',number+1)
    again=import_workbook(pool)
    assert all(n==0 for n in again['inserted_counts'].values())
    final=verify_database(pool)
    assert final['row_counts']['Bookings']==4
    print('All acquired connections returned; workbook rerun inserted zero duplicates.')
    print('Notebook completed without unexpected errors.')
''')
section('11. Conclusion','The actual workbook supports the customer/menu/order/delivery model; supplemental fixtures support the booking routines. Source quality issues, repeated IDs and unknown units remain explicit. The ER diagram and MySQL model agree. Native Workbench and Tableau execution remain NOT VERIFIED. Both existing projects are separate and preserved. See the rubric checklist and evidence files for executed results and limitations.')
nb.cells=cells
nbf.write(nb,ROOT/'notebooks/Little_Lemon_Database.ipynb')
print('Notebook source created:',len(cells),'cells.')
