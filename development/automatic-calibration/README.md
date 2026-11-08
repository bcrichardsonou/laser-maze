# Automatic receiver calibration — installed November 2, 2026

Pi/Mega release: mega-auto-calibration-0.18.0 (bench-0.18.0). Nano remains 0.3.0, manually flashed separately.

One receiver_auto request measures 100 readings each OFF / ON / OFF, after acknowledged module output and 2.5 / 3 / 2.5 second animation settling. Weak, saturated, unstable or drifting samples fail without replacing previous thresholds. Successful proposals persist only after Mega CAL acknowledgement. D, cancellation, local grant expiry and timeout return the module LOW. Existing administrator, CSRF, local C and capability gates remain in force. Only module 1 / A0 is configured.

Validation: 103 Pi tests, 17 release tests, 26 isolated PHP checks; Mega compile uses 14,578 flash bytes and 1,075 RAM bytes. Release archived to portal before flash and copied to Mac. Controller and maintenance worker active; live capability automatic_calibration=true. No physical calibration was initiated. User must aim the beam, enter maintenance, press C, and test the automatic button with path clear. Saved previous thresholds remain untouched.

Portal private backups: backup-20261102-205052-06f8ba and backup-20261102-205222-703d1b under zoco-portal-private/automatic-calibration. Live installed control rendering checked without submitting hardware commands.
