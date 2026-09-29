#!/usr/bin/env python3
"""flowlog: store ntopng's exported flows (journald, facility local3) in SQLite."""
import json, signal, sqlite3, sys
from systemd import journal

DB = "/var/lib/flowlog/flows.db"
BATCH = 500
COLS = ("first_seen last_seen cli_mac srv_mac cli_ip srv_ip cli_port srv_port proto "
        "cli_local srv_local cli_name srv_name app host bytes_c2s bytes_s2c pkts_c2s pkts_s2c "
        "risk_score srv_country http_method http_url community_id ja4c").split()
SCHEMA = f"""
CREATE TABLE IF NOT EXISTS flows ({", ".join(COLS)});
CREATE INDEX IF NOT EXISTS flows_time ON flows(last_seen);
CREATE INDEX IF NOT EXISTS flows_cli ON flows(cli_mac, last_seen);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""
INSERT = f"INSERT INTO flows VALUES ({','.join('?' * len(COLS))})"

def row(d):
    g = d.get
    return (g("FIRST_SWITCHED"), g("LAST_SWITCHED"), g("IN_SRC_MAC"), g("OUT_DST_MAC"),
            g("IPV4_SRC_ADDR") or g("IPV6_SRC_ADDR"), g("IPV4_DST_ADDR") or g("IPV6_DST_ADDR"),
            g("L4_SRC_PORT"), g("L4_DST_PORT"), g("PROTOCOL"),
            int(bool(g("SRC_ADDR_LOCAL"))), int(bool(g("DST_ADDR_LOCAL"))),
            g("SRC_NAME"), g("DST_NAME"), g("L7_PROTO_NAME"),
            g("TLS_SERVER_NAME") or g("HTTP_HOST") or g("DNS_QUERY"),
            g("IN_BYTES", 0), g("OUT_BYTES", 0), g("IN_PKTS", 0), g("OUT_PKTS", 0),
            g("L7_RISK_SCORE", 0), g("DST_IP_COUNTRY") or None,
            g("HTTP_METHOD"), (g("HTTP_URL") or "")[:200] or None,
            g("COMMUNITY_ID"), g("JA4C_HASH"))

def main(once=False):
    db = sqlite3.connect(DB)
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA)
    j = journal.Reader()
    j.add_match(SYSLOG_FACILITY="19")
    saved = db.execute("SELECT value FROM meta WHERE key='cursor'").fetchone()
    saved = saved[0] if saved else None
    if saved:
        j.seek_cursor(saved)
        j.get_next()          # skip the entry we already stored
    else:
        j.seek_head()
    stop = False
    def _stop(*_):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    cursor, total = saved, 0
    while not stop:
        batch = []
        for e in j:
            cursor = e["__CURSOR"]
            try:
                batch.append(row(json.loads(e["MESSAGE"])))
            except (ValueError, TypeError, KeyError, AttributeError):
                pass
            if len(batch) >= BATCH:
                break
        if cursor != saved:
            with db:
                db.executemany(INSERT, batch)
                db.execute("INSERT OR REPLACE INTO meta VALUES ('cursor', ?)", (cursor,))
            saved, total = cursor, total + len(batch)
        if len(batch) < BATCH:
            if once:
                break
            j.wait(5)
    if once:
        n, t0, t1 = db.execute("SELECT count(*), min(first_seen), max(last_seen) FROM flows").fetchone()
        print(f"stored {total} new flows; database holds {n}")
        top = db.execute("SELECT app, sum(bytes_c2s + bytes_s2c) b FROM flows "
                         "GROUP BY app ORDER BY b DESC LIMIT 10").fetchall()
        for app, b in top:
            print(f"{b / 1e6:10.1f} MB  {app}")
    db.close()

if __name__ == "__main__":
    main(once="--once" in sys.argv)
