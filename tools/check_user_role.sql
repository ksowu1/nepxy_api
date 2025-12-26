

SELECT user_id, role, created_at
FROM users.user_roles
WHERE user_id = %(user_id)s::uuid;
