
#db_session.py
from uuid import UUID
from psycopg2.extensions import cursor as Cursor


def set_db_actor(cur: Cursor, user_id: UUID) -> None:
    """
    Sets DB session variable so Postgres can enforce ownership.
    Must be called inside the same connection/transaction before ledger.post_*.
    """
    cur.execute("SELECT set_config('app.user_id', %s, true);", (str(user_id),))
