-- Failing rows only. Return entity_key, detail.
-- Paid invoices carry paid_at. Every other status leaves paid_at empty.

SELECT DISTINCT
    invoice_id AS entity_key,
    status || ' paid_at=' || COALESCE(CAST(paid_at AS VARCHAR), 'NULL') AS detail
FROM invoices
WHERE status IS NOT NULL
  AND (
      (status = 'paid' AND paid_at IS NULL)
      OR (status <> 'paid' AND paid_at IS NOT NULL)
  )
