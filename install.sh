#!/usr/bin/env bash
# flowlog installer: ntopng flow export -> journal -> SQLite -> Grafana. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")"
[ "$(id -u)" -eq 0 ] || { echo "Run with sudo."; exit 1; }
command -v ntopng >/dev/null || { echo "ntopng is not installed."; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Docker with the compose plugin is required."; exit 1; }

echo "1/4 ntopng flow export (syslog facility local3, kept out of /var/log/syslog)"
echo 'local3.* stop' > /etc/rsyslog.d/10-ntopng-flows.conf
systemctl restart rsyslog
if ! grep -q '^-F=' /etc/ntopng/ntopng.conf; then
    echo '-F=syslog;local3' >> /etc/ntopng/ntopng.conf
    systemctl restart ntopng
fi

echo "2/4 loader and housekeeping services"
apt-get install -y -qq python3-systemd >/dev/null
install -d -m 755 /opt/flowlog /opt/flowlog/grafana
install -d -m 750 /var/lib/flowlog
install -m 755 flowlog.py devices.py prune.py dashboard.py /opt/flowlog/
install -m 644 systemd/flowlog.service systemd/flowlog-maint.service systemd/flowlog-maint.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now flowlog.service flowlog-maint.timer
systemctl restart flowlog.service
sleep 5

echo "3/4 device names, database view and dashboard"
cp -r grafana/provisioning grafana/docker-compose.yml /opt/flowlog/grafana/
install -d /opt/flowlog/grafana/provisioning/dashboards/json
python3 /opt/flowlog/devices.py
python3 /opt/flowlog/dashboard.py

echo "4/4 Grafana"
docker rm -f flowlog-grafana >/dev/null 2>&1 || true
docker compose -f /opt/flowlog/grafana/docker-compose.yml up -d
echo "Done. Grafana: http://$(hostname -I | awk '{print $1}'):3030"
