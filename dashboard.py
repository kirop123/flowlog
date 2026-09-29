#!/usr/bin/env python3
"""flowlog: generate the Grafana dashboard that Grafana provisions from /opt/flowlog/grafana."""
import json

OUT = "/opt/flowlog/grafana/provisioning/dashboards/json/flowlog.json"
DS = {"type": "frser-sqlite-datasource", "uid": "flowlog"}
F = ("time >= $__from / 1000 AND time < $__to / 1000 AND scope = 'internet' "
     "AND ('ALL' IN (${device:sqlstring}) OR device IN (${device:sqlstring}))")
DEVQ = "SELECT DISTINCT device FROM v_flows WHERE time > strftime('%s','now') - 604800 ORDER BY 1"
PANELS = [  # type, title, x, y, w, h, query type, SQL, unit
    ("stat", "Downloaded", 0, 0, 6, 4, "table", f"SELECT sum(down) AS downloaded FROM v_flows WHERE {F}", "decbytes"),
    ("stat", "Uploaded", 6, 0, 6, 4, "table", f"SELECT sum(up) AS uploaded FROM v_flows WHERE {F}", "decbytes"),
    ("stat", "Active devices", 12, 0, 6, 4, "table", f"SELECT count(DISTINCT device) AS devices FROM v_flows WHERE {F}", "none"),
    ("stat", "Services seen", 18, 0, 6, 4, "table", f"SELECT count(DISTINCT service) AS services FROM v_flows WHERE {F}", "none"),
    ("timeseries", "Internet traffic by device", 0, 4, 24, 9, "time series",
     f"SELECT $__unixEpochGroupSeconds(time, 300) AS time, device, sum(bytes) * 8 / 300.0 AS bps "
     f"FROM v_flows WHERE {F} GROUP BY 1, 2 ORDER BY 1", "bps"),
    ("table", "Devices", 0, 13, 12, 10, "table",
     f"SELECT device, sum(down) AS download, sum(up) AS upload, sum(bytes) AS total "
     f"FROM v_flows WHERE {F} GROUP BY device ORDER BY total DESC", "decbytes"),
    ("table", "Apps", 12, 13, 12, 10, "table",
     f"SELECT service AS app, sum(bytes) AS total, count(DISTINCT device) AS devices "
     f"FROM v_flows WHERE {F} GROUP BY 1 ORDER BY 2 DESC LIMIT 30", "decbytes"),
    ("table", "Apps by device", 0, 23, 12, 12, "table",
     f"SELECT device, service AS app, sum(bytes) AS total "
     f"FROM v_flows WHERE {F} GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 100", "decbytes"),
    ("table", "Countries", 12, 23, 12, 12, "table",
     f"SELECT COALESCE(NULLIF(country, ''), '?') AS country, sum(bytes) AS total, "
     f"count(DISTINCT device) AS devices FROM v_flows WHERE {F} GROUP BY 1 ORDER BY 2 DESC", "decbytes"),
    ("table", "Latest connections", 0, 35, 24, 12, "table",
     f"SELECT time, device, service AS app, remote, country, bytes, risk_score AS risk "
     f"FROM v_flows WHERE {F} ORDER BY time DESC LIMIT 200", "decbytes"),
]

def panel(i, kind, title, x, y, w, h, qtype, sql, unit):
    p = {"id": i, "type": kind, "title": title, "datasource": DS,
         "gridPos": {"x": x, "y": y, "w": w, "h": h},
         "targets": [{"refId": "A", "datasource": DS, "queryType": qtype,
                      "rawQueryText": sql, "queryText": sql, "timeColumns": ["time"]}],
         "fieldConfig": {"defaults": {"unit": unit}, "overrides": [
             {"matcher": {"id": "byName", "options": n}, "properties": [{"id": "unit", "value": "none"}]}
             for n in ("devices", "risk")]}}
    if kind == "stat":
        p["options"] = {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                        "colorMode": "none", "graphMode": "none", "textMode": "value"}
    elif kind == "timeseries":
        p["fieldConfig"]["defaults"].update({
            "displayName": "${__field.labels.device}",
            "custom": {"drawStyle": "line", "lineWidth": 1, "fillOpacity": 25,
                       "stacking": {"mode": "normal"}}})
        p["options"] = {"legend": {"displayMode": "table", "placement": "right", "calcs": ["mean", "max"]},
                        "tooltip": {"mode": "multi", "sort": "desc"}}
    return p

dash = {"uid": "flowlog", "title": "flowlog - home network", "editable": True,
        "schemaVersion": 39, "version": 1, "refresh": "1m", "timezone": "browser",
        "time": {"from": "now-24h", "to": "now"},
        "templating": {"list": [{"name": "device", "label": "Device", "type": "query",
                                 "datasource": DS, "query": DEVQ, "definition": DEVQ,
                                 "refresh": 2, "includeAll": True, "allValue": "'ALL'", "multi": True, "sort": 1,
                                 "current": {"text": ["All"], "value": ["$__all"]}}]},
        "panels": [panel(i + 1, *p) for i, p in enumerate(PANELS)]}
with open(OUT, "w") as f:
    json.dump(dash, f, indent=1)
print("wrote", OUT)
