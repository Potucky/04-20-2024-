-- Failing rows only. Return entity_key, detail.
-- Null temperatures are ignored. The mammal warning owns missing values.

SELECT DISTINCT
    visit_id AS entity_key,
    CAST(temperature_c AS VARCHAR) AS detail
FROM visits
WHERE temperature_c IS NOT NULL
  AND (
      temperature_c < (SELECT min_temp_c FROM dq_params)
      OR temperature_c > (SELECT max_temp_c FROM dq_params)
  )
