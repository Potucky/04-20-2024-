-- Failing rows only. Return entity_key, detail.

SELECT DISTINCT
    i.invoice_id AS entity_key,
    'invoice patient ' || i.patient_id || ' vs visit patient ' || v.patient_id AS detail
FROM invoices AS i
INNER JOIN visits AS v
    ON i.visit_id = v.visit_id
WHERE i.patient_id IS NOT NULL
  AND v.patient_id IS NOT NULL
  AND i.patient_id <> v.patient_id
