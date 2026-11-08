# Laser Maze dashboard v1

Prepared from the existing ZoCo dashboard and verified game-report format. This add-on does not require a database migration, Pi update, or replacement of lib.php/index.php. It routes only Laser Maze's authorized detailed, unshared exhibit view to the new dashboard. Other exhibit views, basic/shared privacy, and existing portal navigation stay with their live implementation.

## Sections

- Right now: most recent game phase/mode, snapshot countdown, last outcome, two beam inputs/requested outputs.
- Results and trends: today’s test starts, results/wins, challenge win rate, daily starts/results SVG chart, outcome breakdown, timed-win averages, average breaks and mode/timing comparisons.
- Equipment: reporting freshness, Arduino/keypad availability, software versions, temperature/uptime where reported, and collapsed technical metrics.
- Recent games: human-readable session outcomes/durations/breaks, download logs, existing administrator-only remote-access reference, collapsed technical history and retired-component history.

History filters: last 7/30/90 local-calendar days and fast-demo/normal/all timing profiles. The current snapshot is separate from history filters. Starts and results are counted independently by component/session; starts may fall outside the window for a result that lands within it. Wins/beam-limit losses/timeouts form the challenge win-rate denominator. Stops, startup blocks, faults and interruptions are separate. Timed-win averages are split by fast/normal timing. Bench events are never labeled visitor counts.

All statistics use retained raw reports, which have 90-day retention. They are not lifetime totals. The query is bounded to 20,000 matching events per selected window and warns when capped. Delayed uploads can make counts incomplete. The chart is SVG without scripts or inline style attributes, compatible with the existing CSP. Missing/stale/stopped game data is unconfirmed; normal game loss is not a hardware fault. Historical per-beam hit counts are not currently reported, so this dashboard does not invent a beam-hotspot chart.

## Install through the established Bluehost terminal

Copy this folder to `~/zoco-portal-private/portal-dashboard` on Bluehost, preserving `public/views/`, `public/assets/`, and install.php. Staging must remain private. Run:

```sh
php -l ~/zoco-portal-private/portal-dashboard/install.php
php ~/zoco-portal-private/portal-dashboard/install.php
```

The installer checks the exact existing render_exhibit function signature, refuses an existing installation/unexpected target, backs up the live exhibit view into a private dated folder, validates PHP syntax, installs two new assets, then applies a small routing hook. It preserves the rest of the live exhibit view. If any guard fails, inspect the message before proceeding. No credentials are copied or printed. The existing portal source should still provide dashboard.php and remote-access.php helpers; this was confirmed in the saved/live page behavior, but final source compatibility is checked during installation.

Open Laser Maze as an administrator or staff member with detailed access. Check its game figures against raw events, use the timing/date filters, and open Ultimate Design Challenge to confirm its layout still works. Verify basic/shared links do not expose the detailed dashboard. Confirm the existing Software releases navigation link remains.

Recovery: copy the dated backup exhibit.php over the live views/exhibit.php and validate it. New files can remain unused; restoring the view removes the hook. Do not restore a backup over intervening unrelated edits without reviewing them.

## Validation

Eighteen isolated PHP 8.3/SQLite checks pass for counts, duplicate sessions, win denominator, timing separation/filtering, timezone boundaries, invalid/missing records, cross-exhibit exclusion, fresh/stale state, escaped values, finished-progress display, SVG rendering and basic/shared exclusion. PHP syntax checks passed for new view and installer. The generated synthetic preview was inspected at desktop width and 390px phone width; phone document width stayed 390px with no page overflow.

Actual Bluehost installation, deployed-source compatibility, real-data tally verification, query performance and live permissions need the installation checks. This package is not yet installed. The current live page was read and confirmed five bench games, versions bench-0.6.0 and valid start/result payloads.

Reproduce local checks:
```sh
/Users/EXAMPLE_USER/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node development/portal-dashboard/tests/checks.cjs
```
