"""One-time, rerunnable ParkVision migration. Does not modify SQLite."""
import os
import sqlite3
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlsplit, unquote
import pymysql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
url = os.environ.get('DATABASE_URL', '')
parsed = urlsplit(url)
if parsed.scheme not in ('mysql+pymysql', 'mysql') or not parsed.hostname or not parsed.path.strip('/'):
    raise SystemExit('Invalid DATABASE_URL in .env; expected mysql+pymysql://user:password@localhost:3306/parkvision')
source = ROOT / 'bookings.db'
if not source.exists():
    raise SystemExit(f'SQLite source not found: {source}')

def parse_dt(s):
    return datetime.fromisoformat(s)

src = sqlite3.connect(f'file:{source.as_posix()}?mode=ro', uri=True)
src.row_factory = sqlite3.Row
bookings = [dict(r) for r in src.execute('SELECT id,slot_id,customer,start_time,end_time,amount,created_at FROM bookings')]
scans = [dict(r) for r in src.execute('SELECT slot_id,status FROM scan_state')]
src.close()

conn = pymysql.connect(host=parsed.hostname, port=parsed.port or 3306,
    user=unquote(parsed.username or ''), password=unquote(parsed.password or ''),
    database=parsed.path.lstrip('/'), charset='utf8mb4', autocommit=False)
try:
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name IN (\'bookings\',\'scan_state\')')
        if cur.fetchone()[0] != 2:
            raise RuntimeError('Run phase5_schema.sql in MySQL Workbench first.')
        for b in bookings:
            cur.execute(
                """
                INSERT INTO bookings (booking_id,
                                      user_id,
                                      slot_id,
                                      guest_name,
                                      guest_email,
                                      vehicle_number,
                                      start_time,
                                      end_time,
                                      total_price,
                                      status,
                                      created_at)
                VALUES (%s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY
                UPDATE
                    booking_id = booking_id
                """,
                (
                    b["id"],
                    None,
                    b["slot_id"],
                    b["customer"],
                    None,
                    None,
                    parse_dt(b["start_time"]),
                    parse_dt(b["end_time"]),
                    Decimal(str(b["amount"])),
                    "confirmed",
                    parse_dt(b["created_at"])
                )
            )

        for s in scans:

            # Convert SQLite occupancy status to MySQL boolean
            status = str(s["status"]).strip().upper()

            if status == "OCCUPIED":
                is_occupied = 1
            elif status == "EMPTY":
                is_occupied = 0
            else:
                raise ValueError(
                    f"Unknown parking status for slot {s['slot_id']}: {status}"
                )

            cur.execute(
                """
                INSERT INTO scan_state (slot_id, is_occupied)
                VALUES (%s, %s) ON DUPLICATE KEY
                UPDATE
                    is_occupied =
                VALUES (is_occupied)
                """,
                (s["slot_id"], is_occupied)
            )

        if bookings:
            booking_ids = [b["id"] for b in bookings]

            placeholders = ",".join(["%s"] * len(booking_ids))

            cur.execute(
                f"""
                SELECT COUNT(*)
                FROM bookings
                WHERE booking_id IN ({placeholders})
                """,
                booking_ids
            )
        else:
            cur.execute("SELECT 0")
        migrated = cur.fetchone()[0]
        if migrated != len(bookings):
            raise RuntimeError(f'Booking verification failed: {migrated} of {len(bookings)}')
        cur.execute('SELECT COUNT(*) FROM scan_state')
        scan_total = cur.fetchone()[0]
        if scan_total < len(scans):
            raise RuntimeError('Scan verification failed')
    conn.commit()
    print(f'SUCCESS: verified {migrated} SQLite bookings in MySQL; {scan_total} MySQL scan states.')
    print('Original bookings.db was not modified. Existing app.py still uses SQLite until upgraded.')
except Exception:
    conn.rollback()
    raise
finally:
    conn.close()
