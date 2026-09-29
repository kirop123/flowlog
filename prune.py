#!/usr/bin/env python3
"""flowlog: delete flows older than KEEP_DAYS and keep the WAL file small."""
import sqlite3, sys

KEEP_DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 90
db = sqlite3.connect("/var/lib/flowlog/flows.db", timeout=30)
with db:
    n = db.execute("DELETE FROM flows WHERE last_seen < strftime('%s','now') - ? * 86400",
                   (KEEP_DAYS,)).rowcount
db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
db.execute("PRAGMA optimize")
db.close()
print(f"pruned {n} flows older than {KEEP_DAYS} days")
