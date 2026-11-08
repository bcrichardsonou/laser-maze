#!/bin/bash
set -euo pipefail
[[ $(id -u) == 0 ]] || { echo 'Run with sudo.'; exit 1; }
stage=/home/brent/laser-maze/tools
[[ $(/usr/bin/python3 /home/brent/laser-maze/deployments/current/panel_game.py --version) == bench-0.10.0 ]]
[[ ! -e /etc/systemd/system/zoco-maintenance.service ]] || { echo 'Maintenance service already exists; inspect before reinstalling.'; exit 1; }
/usr/bin/systemd-analyze verify "$stage/zoco-maintenance.service"
/usr/bin/install -o root -g root -m 0644 "$stage/zoco-maintenance.service" /etc/systemd/system/zoco-maintenance.service
/usr/bin/systemctl daemon-reload
/usr/bin/systemctl enable --now zoco-maintenance.service
/usr/bin/systemctl status zoco-maintenance.service --no-pager -l
