# Keypad feedback clarification — November 3, 2026

Portal-only update. Hardware diagnostics now has Keypad test · live response: always listening, no Start command, one key at a time with up-to-six-second typical refresh guidance, prominent last key, received timestamp, retained-last-key explanation and staff-control side-effect reminders. Reuses existing last_key/last_key_at telemetry; no firmware deployment or diagnostic command necessary. Lost/stale/disconnected feed clears the displayed key and marks it unconfirmed, including fetch failures. Raw timestamp displayed locally via browser locale.

PHP syntax, existing 37 portal regression checks and JS syntax passed. Exact live-file hash guard plus private backup before activation. Installed administrator rendering verified without sending hardware commands. No physical keypad presses simulated on the Pi. Preview uses synthetic key data to verify the UI independently.
