-- Failing rows only. Return entity_key, detail.

SELECT DISTINCT
    result_id AS entity_key,
    CAST(collected_at AS VARCHAR) AS detail
FROM lab_results
WHERE collected_at IS NOT NULL
  AND collected_at > (SELECT as_of_date FROM dq_params)
