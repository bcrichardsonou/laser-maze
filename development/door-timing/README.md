# Door timing correction — 0.23.1

Installed November 6, 2026. User clarified both doors locked at rest, entry unlock only after successful RFID plus code, exit unlock only at game end; selected a 30-second exit window.

Normal idle: D22 HIGH / D23 HIGH. Successful authorization retains existing five-second preparation, then five-second admission: D22 LOW / D23 HIGH. Running both HIGH. Game end or local stop: D22 HIGH / D23 LOW for 30 seconds, then both HIGH. New games blocked and blue occupied indicator retained for the entire exit window, even if staff clears the result. Fast bench tests omit the hold; actual physical runner is normal timing. Maintenance and controller startup/disarm/watchdog/error release both as in0.23.0. Independent physical exit release must always override software; no position feedback is fitted.

Version bench-0.23.1; release mega-door-timing-0.23.1 privately archived on portal/Pi/Mac before flash. 166 Pi tests,17 deployment tests,host firmware harness and actualMega compile/flash/handshake passed;50PHP regression checks andJS/PHPsyntax passed. Installed admin rendering verified without requesting hardware tests. Allfourservices active; actuallive acknowledgedidle commands=[true,true], exit_release_seconds=0. Physical relay/game/exit-release acceptance still pending. Portal guarded backup door-timing/backup-20261106-132716-2b417e.
