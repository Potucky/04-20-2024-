-- Failing rows only. Return entity_key, detail.

SELECT DISTINCT
    invoice_id AS entity_key,
    'tax=' || CAST(tax_amount AS VARCHAR) || ' amount=' || CAST(amount AS VARCHAR) AS detail
FROM invoices
WHERE tax_amount IS NOT NULL
  AND amount IS NOT NULL
  AND tax_amount > amount
