#!/usr/bin/env python3
"""flowlog: refresh device names from AdGuard's DHCP leases and (re)create the v_flows view."""
import json, sqlite3

DB = "/var/lib/flowlog/flows.db"
LEASES = "/opt/AdGuardHome/data/leases.json"
EXTRA = {"8C:16:45:58:93:C2": "krupas-svr"}
LOCAL = "CASE WHEN f.cli_local = 1 THEN {c} ELSE {s} END"
DEV = LOCAL.format(c="upper(f.cli_mac)", s="upper(f.srv_mac)")
SQL = f"""
CREATE TABLE IF NOT EXISTS devices (mac TEXT PRIMARY KEY, name TEXT NOT NULL,
                                    source TEXT NOT NULL DEFAULT 'manual');
DROP VIEW IF EXISTS v_flows;
CREATE VIEW v_flows AS
SELECT f.last_seen AS time,
       {DEV} AS dev_mac,
       {LOCAL.format(c="f.cli_ip", s="f.srv_ip")} AS dev_ip,
       COALESCE(d.name, NULLIF({LOCAL.format(c="f.cli_name", s="f.srv_name")}, ''),
                {LOCAL.format(c="f.cli_ip", s="f.srv_ip")}, {DEV}, 'unknown') AS device,
       {LOCAL.format(c="f.bytes_c2s", s="f.bytes_s2c")} AS up,
       {LOCAL.format(c="f.bytes_s2c", s="f.bytes_c2s")} AS down,
       f.bytes_c2s + f.bytes_s2c AS bytes,
       COALESCE(f.app, 'Unknown') AS app,
       CASE WHEN instr(f.app, '.') > 0 THEN substr(f.app, instr(f.app, '.') + 1)
            ELSE COALESCE(f.app, 'Unknown') END AS service,
       COALESCE(f.host, {LOCAL.format(c="f.srv_ip", s="f.cli_ip")}) AS remote,
       f.srv_country AS country,
       CASE WHEN f.srv_ip LIKE '224.%' OR f.srv_ip LIKE '239.%' OR f.srv_ip LIKE '255.%'
                 OR f.srv_ip LIKE 'ff%' THEN 'multicast'
            WHEN f.cli_local = 1 AND f.srv_local = 1 THEN 'lan'
            ELSE 'internet' END AS scope,
       f.risk_score, f.http_method, f.http_url
FROM flows f LEFT JOIN devices d ON d.mac = {DEV};
"""
UPSERT = """INSERT INTO devices (mac, name, source) VALUES (?, ?, 'auto')
            ON CONFLICT(mac) DO UPDATE SET name = excluded.name WHERE devices.source = 'auto'"""

db = sqlite3.connect(DB)
with db:
    db.executescript(SQL)
    names = dict(EXTRA)
    try:
        for l in json.load(open(LEASES)).get("leases", []):
            if l.get("mac") and l.get("hostname"):
                names[l["mac"].upper()] = l["hostname"]
    except (OSError, ValueError) as e:
        print("could not read AdGuard leases:", e)
    db.executemany(UPSERT, names.items())
for mac, name, src in db.execute("SELECT mac, name, source FROM devices ORDER BY name"):
    print(f"{mac}  {name:20} {src}")
