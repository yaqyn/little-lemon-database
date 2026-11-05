-- These signatures follow the supplied baseline. No original lab signature sheet was provided.
-- Python owns COMMIT/ROLLBACK; every mutating operation is caller-transactional.
DELIMITER $$
CREATE PROCEDURE IF NOT EXISTS GetMaxQuantity()
BEGIN
    SELECT COALESCE(MAX(Quantity),0) AS MaxQuantity FROM Orders;
END$$

CREATE PROCEDURE IF NOT EXISTS ManageBooking(IN p_BookingDate DATE, IN p_TableNo INT)
BEGIN
    DECLARE v_Booked INT DEFAULT 0;
    IF p_BookingDate IS NULL OR p_TableNo IS NULL OR p_TableNo NOT BETWEEN 1 AND 50 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Supply a date and table number between 1 and 50';
    END IF;
    SELECT COUNT(*) INTO v_Booked FROM Bookings WHERE BookingDate=p_BookingDate AND TableNo=p_TableNo;
    SELECT IF(v_Booked>0,CONCAT('Table ',p_TableNo,' is already booked'),CONCAT('Table ',p_TableNo,' is available')) AS Status,
           (v_Booked>0) AS IsBooked;
END$$

CREATE PROCEDURE IF NOT EXISTS AddBooking(
    IN p_BookingID INT UNSIGNED,
    IN p_CustomerID VARCHAR(32),
    IN p_BookingDate DATE,
    IN p_TableNo INT
)
BEGIN
    IF p_BookingID IS NULL OR p_BookingID=0 OR p_CustomerID IS NULL OR TRIM(p_CustomerID)='' OR p_BookingDate IS NULL
       OR p_TableNo IS NULL OR p_TableNo NOT BETWEEN 1 AND 50 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Supply a positive booking ID, customer ID, date and table 1 through 50';
    END IF;
    IF NOT EXISTS(SELECT 1 FROM Customers WHERE CustomerID=p_CustomerID) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Customer does not exist';
    END IF;
    IF EXISTS(SELECT 1 FROM Bookings WHERE BookingID=p_BookingID) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Booking ID already exists; no record was overwritten';
    END IF;
    IF EXISTS(SELECT 1 FROM Bookings WHERE BookingDate=p_BookingDate AND TableNo=p_TableNo) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='The requested table is already booked on that date';
    END IF;
    INSERT INTO Bookings(BookingID,CustomerID,BookingDate,TableNo) VALUES(p_BookingID,p_CustomerID,p_BookingDate,p_TableNo);
    SELECT p_BookingID AS BookingID, CONCAT('New booking ',p_BookingID,' added; commit required') AS Status;
END$$

CREATE PROCEDURE IF NOT EXISTS UpdateBooking(IN p_BookingID INT UNSIGNED, IN p_NewBookingDate DATE)
BEGIN
    DECLARE v_BookingID INT UNSIGNED DEFAULT NULL;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_BookingID=NULL;
    IF p_BookingID IS NULL OR p_BookingID=0 OR p_NewBookingDate IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Supply a positive booking ID and a new booking date';
    END IF;
    SELECT BookingID INTO v_BookingID FROM Bookings WHERE BookingID=p_BookingID FOR UPDATE;
    IF v_BookingID IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Booking does not exist';
    END IF;
    UPDATE Bookings SET BookingDate=p_NewBookingDate WHERE BookingID=p_BookingID;
    SELECT p_BookingID AS BookingID,CONCAT('Booking ',p_BookingID,' updated; commit required') AS Status;
END$$

CREATE PROCEDURE IF NOT EXISTS CancelBooking(IN p_BookingID INT UNSIGNED)
BEGIN
    DECLARE v_BookingID INT UNSIGNED DEFAULT NULL;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_BookingID=NULL;
    IF p_BookingID IS NULL OR p_BookingID=0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Supply a positive booking ID';
    END IF;
    SELECT BookingID INTO v_BookingID FROM Bookings WHERE BookingID=p_BookingID FOR UPDATE;
    IF v_BookingID IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Booking does not exist';
    END IF;
    DELETE FROM Bookings WHERE BookingID=p_BookingID;
    SELECT p_BookingID AS BookingID,CONCAT('Booking ',p_BookingID,' cancelled; commit required') AS Status;
END$$
DELIMITER ;
