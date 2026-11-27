-- Failing rows only. Return entity_key, detail.
-- Unknown or null species are ignored. Accepted-value and required-field checks own those.

SELECT DISTINCT
    v.visit_id AS entity_key,
    p.species || ' weight_kg=' || CAST(v.weight_kg AS VARCHAR) AS detail
FROM visits AS v
INNER JOIN patients AS p
    ON v.patient_id = p.patient_id
INNER JOIN dq_weight_bounds AS b
    ON b.species = p.species
WHERE v.weight_kg IS NOT NULL
  AND (v.weight_kg < b.min_kg OR v.weight_kg > b.max_kg)
