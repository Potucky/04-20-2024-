-- Failing rows only. Return entity_key, detail.

SELECT DISTINCT
    i.invoice_id AS entity_key,
    'visit status=' || v.status AS detail
FROM invoices AS i
INNER JOIN visits AS v
    ON i.visit_id = v.visit_id
WHERE v.status IS NOT NULL
  AND v.status <> 'completed'
