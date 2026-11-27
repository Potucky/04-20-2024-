-- Failing rows only. Return entity_key, detail.

SELECT DISTINCT
    patient_id AS entity_key,
    CAST(date_of_birth AS VARCHAR) AS detail
FROM patients
WHERE date_of_birth IS NOT NULL
  AND date_of_birth < (SELECT min_birth_date FROM dq_params)
