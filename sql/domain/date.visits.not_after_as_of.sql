-- Failing rows only. Return entity_key, detail.

SELECT DISTINCT
    visit_id AS entity_key,
    CAST(visit_date AS VARCHAR) AS detail
FROM visits
WHERE visit_date IS NOT NULL
  AND visit_date > (SELECT as_of_date FROM dq_params)
