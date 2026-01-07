

$code = @"
from db import get_conn

def main():
    with get_conn() as conn:
        cur = conn.cursor()

        # Add the column the admin query expects
        cur.execute("ALTER TABLE app.webhook_events ADD COLUMN IF NOT EXISTS signature_valid boolean;")

        # Optional: backfill existing rows to avoid NULL surprises
        cur.execute("UPDATE app.webhook_events SET signature_valid = TRUE WHERE signature_valid IS NULL;")

        # Optional: default for new rows
        cur.execute("ALTER TABLE app.webhook_events ALTER COLUMN signature_valid SET DEFAULT TRUE;")

        conn.commit()

    print("✅ migrated: app.webhook_events.signature_valid")

if __name__ == "__main__":
    main()
"@

Set-Content -Path .\_migrate_webhook_events_signature_valid.py -Value $code -Encoding UTF8
python .\_migrate_webhook_events_signature_valid.py
