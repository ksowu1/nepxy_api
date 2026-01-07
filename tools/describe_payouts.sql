


SELECT
  column_name,
  data_type,
  is_nullable,
  column_default
FROM information_schema.columns
WHERE table_schema = 'app'
  AND table_name = 'mobile_money_payouts'
ORDER BY ordinal_position;
