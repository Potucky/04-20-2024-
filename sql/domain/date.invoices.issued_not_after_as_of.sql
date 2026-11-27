-- Failing rows only. Return entity_key, detail.

SELECT DISTINCT
    invoice_id AS entity_key,
    CAST(issued_at AS VARCHAR) AS detail
FROM invoices
WHERE issued_at IS NOT NULL
  AND issued_at > (SELECT as_of_date FROM dq_params)
