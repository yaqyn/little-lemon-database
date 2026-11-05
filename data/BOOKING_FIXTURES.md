# Supplemental booking fixtures

The workbook contains no booking IDs, restaurant table numbers, booking-to-order
links, staff assignments, or employee records. The four records in
`sql/seed_data.sql` are explicitly **demonstration booking fixtures**, not imported
course booking data. Their customer IDs reference existing workbook customers;
the dates and table numbers are invented solely to exercise the required routines.
The workbook's customers, menus, orders and delivery dates remain separate,
source-derived records. No booking-to-order relationship is inferred.

Bookings are unique by date and table for this assignment. This full-day rule
matches the supplied procedure baseline and differs from the existing capstone's
hour-slot rule. Historical dates are allowed, so examples using course-era dates
remain executable. No original detailed lab signature sheet was available;
procedure parameters are documented explicitly rather than claimed as confirmed
hidden-grader signatures.
