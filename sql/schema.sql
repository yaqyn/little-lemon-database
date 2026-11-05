-- Source-aware schema for the provided workbook; no invented per-component prices.
CREATE TABLE IF NOT EXISTS Customers (
    CustomerID VARCHAR(32) NOT NULL PRIMARY KEY,
    CustomerName VARCHAR(150) NOT NULL,
    City VARCHAR(150) NOT NULL,
    Country VARCHAR(150) NOT NULL,
    CountryCode VARCHAR(8) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS MenuItems (
    ItemID INT UNSIGNED NOT NULL PRIMARY KEY,
    ItemName VARCHAR(150) NOT NULL,
    ItemType VARCHAR(20) NOT NULL,
    UNIQUE KEY uq_item_role (ItemID, ItemType),
    CONSTRAINT chk_item_type CHECK (ItemType IN ('Course','Starter','Dessert','Drink','Side'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS Menus (
    MenuID INT UNSIGNED NOT NULL PRIMARY KEY,
    CuisineName VARCHAR(100) NOT NULL,
    BundleKey CHAR(64) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS MenuComponents (
    MenuID INT UNSIGNED NOT NULL,
    ComponentRole VARCHAR(20) NOT NULL,
    ItemID INT UNSIGNED NOT NULL,
    PRIMARY KEY (MenuID, ComponentRole),
    CONSTRAINT fk_component_menu FOREIGN KEY (MenuID) REFERENCES Menus(MenuID),
    CONSTRAINT fk_component_item_role FOREIGN KEY (ItemID, ComponentRole) REFERENCES MenuItems(ItemID, ItemType)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS Orders (
    -- The workbook's unique Row Number is our record key. Source IDs repeat.
    OrderID INT UNSIGNED NOT NULL PRIMARY KEY,
    SourceOrderID VARCHAR(32) NOT NULL,
    CustomerID VARCHAR(32) NOT NULL,
    MenuID INT UNSIGNED NOT NULL,
    OrderDate DATE NOT NULL,
    PostalCodeRaw VARCHAR(64) NOT NULL,
    Cost DECIMAL(18,4) NOT NULL,
    Sales DECIMAL(18,4) NOT NULL,
    Quantity SMALLINT UNSIGNED NOT NULL,
    Discount DECIMAL(18,4) NOT NULL,
    DeliveryCost DECIMAL(18,4) NOT NULL,
    KEY ix_source_order (SourceOrderID),
    CONSTRAINT fk_order_customer FOREIGN KEY (CustomerID) REFERENCES Customers(CustomerID),
    CONSTRAINT fk_order_menu FOREIGN KEY (MenuID) REFERENCES Menus(MenuID),
    CONSTRAINT chk_source_row CHECK (OrderID > 0),
    CONSTRAINT chk_order_quantity CHECK (Quantity > 0),
    CONSTRAINT chk_order_measures CHECK (Cost >= 0 AND Sales >= 0 AND Discount >= 0 AND DeliveryCost >= 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS OrderDeliveryStatus (
    OrderID INT UNSIGNED NOT NULL PRIMARY KEY,
    DeliveryDate DATE NOT NULL,
    CONSTRAINT fk_delivery_order FOREIGN KEY (OrderID) REFERENCES Orders(OrderID)
    -- Only a date is supplied; no delivery status is invented.
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS Bookings (
    BookingID INT UNSIGNED NOT NULL PRIMARY KEY,
    CustomerID VARCHAR(32) NOT NULL,
    BookingDate DATE NOT NULL,
    TableNo TINYINT UNSIGNED NOT NULL,
    CONSTRAINT fk_booking_customer FOREIGN KEY (CustomerID) REFERENCES Customers(CustomerID),
    CONSTRAINT uq_booking_date_table UNIQUE (BookingDate, TableNo),
    CONSTRAINT chk_booking_id CHECK (BookingID > 0),
    CONSTRAINT chk_booking_table CHECK (TableNo BETWEEN 1 AND 50)
) ENGINE=InnoDB;
