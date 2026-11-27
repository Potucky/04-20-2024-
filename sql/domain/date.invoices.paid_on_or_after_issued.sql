-- Failing rows only. Return entity_key, detail.
-- A null paid_at is ignored. The status consistency check owns that case.

SELECT DISTINCT
    invoice_id AS entity_key,
    CAST(paid_at AS VARCHAR) || ' before issued ' || CAST(issued_at AS VARCHAR) AS detail
FROM invoices
WHERE paid_at IS NOT NULL
  AND issued_at IS NOT NULL
  AND paid_at < issued_at
