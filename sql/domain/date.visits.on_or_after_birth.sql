-- Failing rows only. Return entity_key, detail.
-- Orphan visits are ignored. The foreign-key check owns those.

SELECT DISTINCT
    v.visit_id AS entity_key,
    CAST(v.visit_date AS VARCHAR) || ' before birth ' || CAST(p.date_of_birth AS VARCHAR) AS detail
FROM visits AS v
INNER JOIN patients AS p
    ON v.patient_id = p.patient_id
WHERE v.visit_date IS NOT NULL
  AND p.date_of_birth IS NOT NULL
  AND v.visit_date < p.date_of_birth
