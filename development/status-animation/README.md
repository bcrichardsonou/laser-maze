# Symmetric 42-pixel status light — November 4, 2026

Mega D6 controls 42 WS2812 pixels at brightness 255, arranged as 14 consecutive rows of three. Index0 is the bottom. Rows0–6 are bottom half,7–13 top half. No Nano module-ring changes.

Blue, green and purple use a 700ms center-out bloom: center row pair6/7 first, then5/8 through0/13, with smoothstep blending across a two-pair soft edge. Red and yellow use two bottom/top alternations at250ms per half, followed by250ms settling to a solid color (1.25s total). Dim half remains at32/255 during wig-wag. Colors remain solid between transitions; repeated same-color commands do not restart animation. Mid-animation retargeting snapshots each current row. OFF/disarm/watchdog clears immediately, without an animated delay. All game-state colors and gameplay timings unchanged.

42 pixels require about1.3ms interrupt-masked output on AVR. Final release0.20.1 uses an explicit FRAME/OK FRAME exchange scheduled only when the Pi serial request pipeline is empty. Other writes defer until FRAME acknowledgement. Frames are requested for1.4s after color changes, with20ms minimum spacing; actual refresh follows serial loop timing. No blocking delays or extra startup queries, no stable-color redundant pixel transmissions.

Host firmware tests cover42 pixels, row uniformity, center symmetry, bloom endpoints, alternating halves, interrupted transitions, repeated targets, immediate OFF and timer wrap.137Pi tests (including frame/request exclusion and deferred callbacks) and17release tests passed. Physical visual acceptance remains for user. Initial0.20.0 archive has uncoordinated background refresh; superseded by0.20.1 for serial protection.

Deployment verified: actual AVR compile16,182flash/1,152static RAM, live bench-0.20.1 connected and reporting42pixels/14rows, game and monitoring active. Archives retained on Bluehost/Pi/Mac.
