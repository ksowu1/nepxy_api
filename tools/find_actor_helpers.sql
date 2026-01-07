SELECT
  n.nspname AS schema,
  p.proname AS name,
  pg_get_function_identity_arguments(p.oid) AS args
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE p.proname ILIKE '%session%'
   OR p.proname ILIKE '%current%'
   OR p.proname ILIKE '%actor%'
   OR p.proname ILIKE '%jwt%'
ORDER BY n.nspname, p.proname;
