"""Demonstrate the five required routines using only a temporary booking."""
from datetime import date,timedelta
from pathlib import Path
import secrets
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mysql.connector import Error
from python.database import create_pool,pooled_cursor,call_procedure


def demonstrate_procedures(pool):
    call_procedure(pool,'GetMaxQuantity')
    call_procedure(pool,'ManageBooking',('2022-10-10',1))
    with pooled_cursor(pool) as (_,cursor):
        cursor.execute('SELECT CustomerID FROM Customers ORDER BY CustomerID LIMIT 1')
        customer=cursor.fetchone()[0]
        while True:
            booking_id=1_100_000_000+secrets.randbelow(100_000_000)
            day=date.today()+timedelta(days=365+secrets.randbelow(1000))
            cursor.execute('SELECT COUNT(*) FROM Bookings WHERE BookingID=%s OR (TableNo=48 AND BookingDate IN (%s,%s))',(booking_id,day,day+timedelta(days=1)))
            if cursor.fetchone()[0]==0:break
    created=False
    try:
        call_procedure(pool,'ManageBooking',(day,48))
        call_procedure(pool,'AddBooking',(booking_id,customer,day,48),commit=True)
        created=True
        call_procedure(pool,'ManageBooking',(day,48))
        call_procedure(pool,'UpdateBooking',(booking_id,day+timedelta(days=1)),commit=True)
        with pooled_cursor(pool) as (_,cursor):
            cursor.execute('SELECT BookingDate FROM Bookings WHERE BookingID=%s',(booking_id,))
            assert cursor.fetchone()[0]==day+timedelta(days=1)
            print('Updated date persisted to a subsequent pooled checkout.')
        call_procedure(pool,'CancelBooking',(booking_id,),commit=True)
        created=False
        for name,args in [('UpdateBooking',(booking_id,day)),('CancelBooking',(booking_id,))]:
            try:call_procedure(pool,name,args,commit=True)
            except Error as er:
                print('Expected missing-booking result:',er.errno,er.msg)
            else:raise AssertionError('A missing booking must not report success.')
        print('All five procedures executed; temporary booking removed.')
    finally:
        if created:call_procedure(pool,'CancelBooking',(booking_id,),commit=True)
    return {'procedures_executed':5,'temporary_booking_removed':True}


if __name__=='__main__':
    demonstrate_procedures(create_pool())
