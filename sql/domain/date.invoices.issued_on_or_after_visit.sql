-- Failing rows only. Return entity_key, detail.

SELECT DISTINCT
    i.invoice_id AS entity_key,
    CAST(i.issued_at AS VARCHAR) || ' before visit ' || CAST(v.visit_date AS VARCHAR) AS detail
FROM invoices AS i
INNER JOIN visits AS v
    ON i.visit_id = v.visit_id
WHERE i.issued_at IS NOT NULL
  AND v.visit_date IS NOT NULL
  AND i.issued_at < v.visit_date
