-- Failing rows only. Return entity_key, detail.

SELECT DISTINCT
    visit_id AS entity_key,
    'completed visit has no weight_kg' AS detail
FROM visits
WHERE status = 'completed'
  AND weight_kg IS NULL
