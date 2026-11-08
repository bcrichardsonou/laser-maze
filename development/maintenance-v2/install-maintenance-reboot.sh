#!/bin/bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo 'Run this installer with sudo.' >&2; exit 1; fi
policy=/etc/sudoers.d/zoco-maintenance-reboot
line='brent ALL=(root) NOPASSWD: /usr/bin/systemctl reboot --no-block'
stage=$(mktemp /etc/sudoers.d/.zoco-reboot.XXXXXX)
trap 'rm -f "$stage"' EXIT
printf '%s\n' "$line" > "$stage"
chmod 440 "$stage"
/usr/sbin/visudo -cf "$stage"
if [[ -e "$policy" ]] && ! cmp -s "$stage" "$policy"; then
  echo 'Existing reboot policy differs; original unchanged.' >&2; exit 1
fi
install -o root -g root -m 440 "$stage" "$policy"
/usr/sbin/visudo -c
systemctl restart zoco-maintenance.service
printf 'Scoped reboot permission installed. No reboot was performed.\n'
