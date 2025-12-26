-- 1) show the secure function body (so we can see which table it writes to)
SELECT pg_get_functiondef('users.set_user_role_secure(uuid,text)'::regprocedure) AS set_user_role_secure_def;

-- 2) list candidate role tables
SELECT
  n.nspname AS schema,
  c.relname AS table
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r'
  AND (
    c.relname ILIKE '%role%'
    OR c.relname ILIKE '%permission%'
  )
ORDER BY 1,2;

-- 3) list candidate functions (maybe there is a non-secure/internal one)
SELECT
  n.nspname AS schema,
  p.proname AS func,
  oidvectortypes(p.proargtypes) AS args
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname IN ('users','app')
  AND (
    p.proname ILIKE '%role%'
    OR p.proname ILIKE '%admin%'
    OR p.proname ILIKE '%permission%'
  )
ORDER BY 1,2,3;
