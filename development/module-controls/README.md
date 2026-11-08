# Laser module portal controls — November 2, 2026

Installed on Bluehost with guarded hash checks and rollback backup `~/zoco-portal-private/module-controls/backup-20261102-203022-46ec5f`.

Replaces misleading ring customization placeholders with shared module selector and selected/all HIGH/LOW forms. Separate entrance-status-light color test retained in its own group. Controller currently advertises exactly one real module. Selected/all HIGH reuse existing `laser_align` (30s automatic LOW); selected/all LOW reuse existing priority `stop_game` (cancel tests/game). No new Pi/Mega protocol, no firmware update, no hardware test executed. Future controllers advertising multiple modules are rejected for HIGH until per-module backend support is implemented; global LOW remains the existing stop. Do not represent this as 15-channel control support.

`module_control` is only a portal request adapter; strict scope/module/boolean checks and fresh powered-calibration capability are required, then standard admin/CSRF/rate-limit/local-confirmation/queue controls apply to the existing command. LOW remains available during pending commands. The shared selector currently contains only supported module1. Source updated in development/maintenance/public for future upgrades.

Checks:16 isolated server PHP checks;PHP lint;Node syntax;browser synthetic preview tested all-HIGH payload and pending-state LOW availability;installed administrator render and fresh capabilities verified with read-only private CLI helper. Existing 30s command hardware behavior not retested in this change. No database schema/config changes, game restart or Pi deployment.
