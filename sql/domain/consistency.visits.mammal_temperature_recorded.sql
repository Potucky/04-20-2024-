-- Failing rows only. Return entity_key, detail.
-- Warning severity. Dogs, cats, and rabbits should have a temperature
-- on a completed visit. Reptile visits are outside this rule.

SELECT DISTINCT
    v.visit_id AS entity_key,
    p.species || ' completed without temperature_c' AS detail
FROM visits AS v
INNER JOIN patients AS p
    ON v.patient_id = p.patient_id
INNER JOIN dq_temp_required_species AS s
    ON s.species = p.species
WHERE v.status = 'completed'
  AND v.temperature_c IS NULL
