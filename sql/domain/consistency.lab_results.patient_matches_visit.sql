-- Failing rows only. Return entity_key, detail.

SELECT DISTINCT
    l.result_id AS entity_key,
    'lab patient ' || l.patient_id || ' vs visit patient ' || v.patient_id AS detail
FROM lab_results AS l
INNER JOIN visits AS v
    ON l.visit_id = v.visit_id
WHERE l.patient_id IS NOT NULL
  AND v.patient_id IS NOT NULL
  AND l.patient_id <> v.patient_id
