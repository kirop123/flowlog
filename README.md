# flowlog

Keeps a searchable history of every network flow that ntopng Community sees, and shows
per-device usage, apps and trends in Grafana. Community edition only keeps live flows in
memory; flowlog fills that gap.

    ntopng (-F syslog;local3) -> systemd journal -> flowlog.py -> SQLite -> Grafana

## Parts
- `flowlog.py`: service that reads ntopng's exported flows from the journal into
  `/var/lib/flowlog/flows.db`. It stores its journal position with each write, so
  restarts neither lose nor duplicate flows.
- `devices.py`: names devices from AdGuard Home's DHCP leases and (re)creates the
  `v_flows` view (device, upload/download, service, scope).
- `prune.py`: deletes flows older than N days (default 90).
- `dashboard.py`: generates the Grafana dashboard.
- `systemd/`: the loader service and an hourly housekeeping timer.
- `grafana/`: Docker Compose file and provisioning (SQLite plugin, data source, dashboard).

## Requirements
Ubuntu (tested on 24.04) with systemd, ntopng 6+ (tested with 7.0 Community) capturing the LAN,
and Docker with the compose plugin. AdGuard Home is optional (device names).

## Install
    sudo ./install.sh

Grafana then runs on port 3030 (first login admin/admin).

## Usage
- Rename a device so the hourly refresh keeps your name:
  `INSERT INTO devices (mac, name, source) VALUES ('AA:BB:CC:DD:EE:FF', 'My laptop', 'manual')
   ON CONFLICT(mac) DO UPDATE SET name = excluded.name, source = 'manual';`
- Retention: change the `90` in `systemd/flowlog-maint.service`.

## Privacy
The database holds every device's browsing metadata (sites, apps, times). Keep Grafana
behind its login and don't expose port 3030 to the internet.
