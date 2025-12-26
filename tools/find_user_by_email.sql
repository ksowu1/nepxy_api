

SELECT id, email
FROM users.users
WHERE email = %(email)s;
