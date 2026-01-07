SELECT
  n.nspname AS schema,
  p.proname AS name,
  pg_get_function_identity_arguments(p.oid) AS args
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE p.proname ILIKE '%db_actor%'
   OR p.proname ILIKE '%set_actor%'
   OR p.proname ILIKE '%set_session%'
ORDER BY n.nspname, p.proname;
