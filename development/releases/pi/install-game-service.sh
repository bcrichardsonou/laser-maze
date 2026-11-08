#!/bin/bash
set -euo pipefail
if [[ $(id -u) != 0 ]]; then
    echo 'Run: sudo bash ~/laser-maze/tools/install-game-service.sh'
    exit 1
fi
stage=/home/brent/laser-maze/tools
current=/home/brent/laser-maze/deployments/current
[[ -f "$current/panel_game.py" ]]
[[ $(/usr/bin/python3 "$current/panel_game.py" --version) == bench-0.7.0 ]]
/usr/sbin/visudo -cf "$stage/zoco-game-sudoers"
/usr/bin/systemd-analyze verify "$stage/zoco-game.service"
for target in /etc/systemd/system/zoco-game.service /etc/sudoers.d/zoco-game; do
    if [[ -e $target ]]; then
        echo "Service setup already exists: $target. Review it before reinstalling."
        exit 1
    fi
done
/usr/bin/install -o root -g root -m 0440 "$stage/zoco-game-sudoers" /etc/sudoers.d/zoco-game
/usr/bin/install -o root -g root -m 0644 "$stage/zoco-game.service" /etc/systemd/system/zoco-game.service
/usr/bin/systemctl daemon-reload
/usr/bin/systemctl enable --now zoco-game.service
/usr/bin/python3 - <<'PY'
import json,time
from pathlib import Path
path=Path('/home/brent/zoco-monitor/laser-maze/game-status.json')
for _ in range(30):
    try:
        data=json.loads(path.read_text());metrics=data.get('metrics',{})
        if time.time()-path.stat().st_mtime<15 and metrics.get('python_version')=='bench-0.7.0' and metrics.get('arduino_connected') is True and metrics.get('game_phase')=='idle':
            print('Game service ready: Arduino responding; idle, waiting for A to start. Normal timing is 150 seconds.')
            break
    except (OSError,ValueError):pass
    time.sleep(.5)
else:
    raise SystemExit('Service installed, but idle controller status was not confirmed. Inspect: journalctl -u zoco-game -n 30 --no-pager')
PY
/usr/bin/systemctl status zoco-game.service --no-pager -l
