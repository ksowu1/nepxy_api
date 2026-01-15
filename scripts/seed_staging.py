import os
import sys
import uuid

from db import get_conn
from security import hash_password


def die(message, code=1):
    print(message)
    sys.exit(code)


def _get_env(name, default=None):
    return os.getenv(name, default)


def _get_user_by_email(cur, email):
    cur.execute("SELECT id FROM users.users WHERE email = %s LIMIT 1;", (email,))
    row = cur.fetchone()
    return row[0] if row else None


def _ensure_wallet(cur, user_id, country):
    cur.execute(
        """
        SELECT id FROM ledger.ledger_accounts
        WHERE owner_type = 'USER'
          AND owner_id = %s::uuid
          AND account_type = 'WALLET'
        LIMIT 1;
        """,
        (str(user_id),),
    )
    row = cur.fetchone()
    if row:
        return row[0], False

    cur.execute(
        """
        INSERT INTO ledger.ledger_accounts
          (owner_type, owner_id, country, currency, account_type, is_active)
        VALUES
          ('USER', %s::uuid, %s::ledger.country_code, 'XOF', 'WALLET', TRUE)
        RETURNING id;
        """,
        (str(user_id), country),
    )
    wallet_id = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO ledger.wallet_balances(account_id, available_cents, pending_cents, updated_at)
        VALUES (%s::uuid, 0, 0, now())
        ON CONFLICT (account_id) DO NOTHING;
        """,
        (str(wallet_id),),
    )
    return wallet_id, True


def _ensure_user(cur, *, email, password, phone, full_name, country):
    user_id = _get_user_by_email(cur, email)
    if user_id:
        return user_id, False

    pw_hash = hash_password(password)
    cur.execute(
        """
        SELECT users.register_user_secure(
          %s::text,
          %s::text,
          %s::text,
          %s::ledger.country_code,
          %s::text
        );
        """,
        (email, phone, full_name, country, pw_hash),
    )
    user_id = cur.fetchone()[0]
    return user_id, True


def _ensure_admin_role(cur, user_id):
    cur.execute(
        """
        INSERT INTO users.user_roles (user_id, role)
        VALUES (%s::uuid, 'ADMIN')
        ON CONFLICT (user_id) DO UPDATE SET role = EXCLUDED.role;
        """,
        (str(user_id),),
    )


def main():
    admin_email = _get_env("STAGING_ADMIN_EMAIL", "admin@nexapay.io")
    admin_password = _get_env("STAGING_ADMIN_PASSWORD", "ChangeMe123!")
    admin_phone = _get_env("STAGING_ADMIN_PHONE", f"+1555{uuid.uuid4().int % 10_000_000:07d}")

    user_email = _get_env("STAGING_USER_EMAIL", "staging-user@nexapay.io")
    user_password = _get_env("STAGING_USER_PASSWORD", "ChangeMe123!")
    user_phone = _get_env("STAGING_USER_PHONE", f"+1555{uuid.uuid4().int % 10_000_000:07d}")

    country = _get_env("STAGING_COUNTRY", "TG")

    with get_conn() as conn:
        with conn.cursor() as cur:
            admin_id, admin_created = _ensure_user(
                cur,
                email=admin_email,
                password=admin_password,
                phone=admin_phone,
                full_name="Staging Admin",
                country=country,
            )
            _ensure_admin_role(cur, admin_id)
            admin_wallet_id, admin_wallet_created = _ensure_wallet(cur, admin_id, country)

            user_id, user_created = _ensure_user(
                cur,
                email=user_email,
                password=user_password,
                phone=user_phone,
                full_name="Staging User",
                country=country,
            )
            user_wallet_id, user_wallet_created = _ensure_wallet(cur, user_id, country)

        conn.commit()

    print("Admin:")
    if admin_created:
        print(f"  created email={admin_email} password={admin_password} user_id={admin_id}")
    else:
        print(f"  exists email={admin_email} user_id={admin_id}")
    print(f"  wallet_id={admin_wallet_id} created={admin_wallet_created}")

    print("User:")
    if user_created:
        print(f"  created email={user_email} password={user_password} user_id={user_id}")
    else:
        print(f"  exists email={user_email} user_id={user_id}")
    print(f"  wallet_id={user_wallet_id} created={user_wallet_created}")


if __name__ == "__main__":
    main()
