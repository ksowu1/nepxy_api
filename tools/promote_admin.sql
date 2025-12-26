

INSERT INTO users.user_roles (user_id, role)
VALUES (%(user_id)s::uuid, 'ADMIN')
ON CONFLICT (user_id) DO UPDATE
SET role = EXCLUDED.role;
