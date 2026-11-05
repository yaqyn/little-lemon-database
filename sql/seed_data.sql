-- Supplemental booking examples only. The workbook contains no booking records.
-- Customers are genuine IDs from the provided workbook; dates/tables are demo fixtures.
INSERT INTO Bookings(BookingID,CustomerID,BookingDate,TableNo)
SELECT 1,'00-090-3491','2022-10-10',1 WHERE NOT EXISTS(SELECT 1 FROM Bookings WHERE BookingID=1);
INSERT INTO Bookings(BookingID,CustomerID,BookingDate,TableNo)
SELECT 2,'00-352-9063','2022-11-12',3 WHERE NOT EXISTS(SELECT 1 FROM Bookings WHERE BookingID=2);
INSERT INTO Bookings(BookingID,CustomerID,BookingDate,TableNo)
SELECT 3,'00-381-6823','2022-10-11',2 WHERE NOT EXISTS(SELECT 1 FROM Bookings WHERE BookingID=3);
INSERT INTO Bookings(BookingID,CustomerID,BookingDate,TableNo)
SELECT 4,'00-435-7006','2022-10-13',2 WHERE NOT EXISTS(SELECT 1 FROM Bookings WHERE BookingID=4);
