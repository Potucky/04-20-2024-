-- Failing rows only. Return entity_key, detail.

SELECT DISTINCT
    l.result_id AS entity_key,
    CAST(l.collected_at AS VARCHAR) || ' before visit ' || CAST(v.visit_date AS VARCHAR) AS detail
FROM lab_results AS l
INNER JOIN visits AS v
    ON l.visit_id = v.visit_id
WHERE l.collected_at IS NOT NULL
  AND v.visit_date IS NOT NULL
  AND l.collected_at < v.visit_date
