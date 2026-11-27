-- Failing rows only. Return entity_key, detail.

SELECT DISTINCT
    v.visit_id AS entity_key,
    'completed visit has no invoice' AS detail
FROM visits AS v
LEFT JOIN invoices AS i
    ON i.visit_id = v.visit_id
WHERE v.status = 'completed'
  AND i.invoice_id IS NULL
