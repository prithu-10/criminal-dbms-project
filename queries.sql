-- =================================================================
-- 1. SIMPLE SELECT...WHERE
-- (Finds a specific criminal by their name)
-- =================================================================
SELECT *
FROM Criminal
WHERE FirstName = 'Ram Bahadur' AND LastName = 'Thapa';


-- =================================================================
-- 2. ADVANCED JOIN (Criminals & Cases)
-- (Finds all cases associated with a specific criminal)
-- =================================================================
SELECT
    ct.CaseTitle,
    ct.Status,
    cc.Role
FROM CaseTable ct
JOIN CriminalCase cc ON ct.CaseID = cc.CaseID
JOIN Criminal c ON cc.CriminalID = c.CriminalID
WHERE c.FirstName = 'Ram Bahadur' AND c.LastName = 'Thapa';


-- =================================================================
-- 3. AGGREGATE with GROUP BY
-- (Counts how many cases are at each location)
-- =================================================================
SELECT
    l.City,
    l.Address,
    COUNT(ct.CaseID) AS NumberOfCases
FROM Location l
JOIN CaseTable ct ON l.LocationID = ct.LocationID
GROUP BY l.City, l.Address
ORDER BY NumberOfCases DESC;


-- =================================================================
-- 4. NESTED QUERY / SUBQUERY (FIXED - This is the better example)
-- (Finds all criminals who are involved in cases that are still open)
-- =================================================================
SELECT FirstName, LastName, NationalID
FROM Criminal
WHERE CriminalID IN (
    SELECT DISTINCT CriminalID
    FROM CriminalCase
    WHERE CaseID IN (
        SELECT CaseID
        FROM CaseTable
        WHERE Status = 'Open'
    )
);


-- =================================================================
-- 5. CREATE VIEW
-- (Creates a simple, virtual table for "Active Cases")
-- =================================================================
CREATE VIEW view_ActiveCases AS
SELECT
    ct.CaseNumber,
    ct.CaseTitle,
    ct.DateReported,
    l.City,
    l.Address
FROM CaseTable ct
JOIN Location l ON ct.LocationID = ct.LocationID
WHERE ct.Status = 'Open' OR ct.Status = 'Under Investigation';


-- =================================================================
-- 6. QUERY from VIEW
-- (Using the view is much simpler than writing the JOIN again)
-- =================================================================
SELECT * FROM view_ActiveCases
WHERE City = 'Kathmandu';


-- =================================================================
-- 7. UPDATE Statement
-- (Changes a criminal's status from 'At Large' to 'In Custody')
-- =================================================================
UPDATE Criminal
SET Status = 'In Custody'
WHERE FirstName = 'Gopal' AND LastName = 'Shrestha';


-- =================================================================
-- 8. DELETE Statement
-- (Deletes a low-severity crime. This will also be removed
-- from 'CaseCrime' junction table due to 'ON DELETE CASCADE')
-- =================================================================
DELETE FROM Crime
WHERE CrimeType = 'Vandalism';


-- =================================================================
-- 9. USING A STORED PROCEDURE
-- (Demonstrates calling the procedure you already wrote)
-- =================================================================
-- This code adds a new criminal AND links them to Case #4
SELECT sp_AddCriminalWithCase(
    'New', 'Suspect', '1999-01-01', 'Male', 'NPL999999',
    'Unknown Address', 'At Large', 'Medium',
    4, -- The CaseID to link to
    'New Suspect' -- The role in that case
);


-- =================================================================
-- 10. DEMONSTRATING A TRIGGER (Explanation)
-- (This query will automatically fire your 'fn_update_timestamp' trigger)
-- =================================================================
-- Run this query:
UPDATE Criminal
SET Address = 'New Address for Ram'
WHERE CriminalID = 1;

-- Then run this query to see the result:
SELECT FirstName, CreatedAt, UpdatedAt
FROM Criminal
WHERE CriminalID = 1;

-- You will see that 'UpdatedAt' is now newer than 'CreatedAt',
-- proving the trigger worked automatically.