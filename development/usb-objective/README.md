# Real USB drive objective — installed November 5, 2026

mega-usb-objective-0.22.0 / bench-0.22.0 replaces the D4 latching button with Pi USB mass-storage detection at the visitor extension socket. Firmware D4 is neither configured nor read; third INPUTS wire-protocol value remains false for compatibility. Python overlays input3 with actual USB presence and never uses the serial third input for a game objective. Existing latch_active telemetry key retained for portal schema compatibility, now reflecting USB presence.

Pure Python sysfs observer polls100ms; reads controller topology, USB descriptor paths and block-device metadata only. Never opens/mounts drive files, and stores no visitor device serial/UUID. Runtime control/usb-port.json binds stable controller+USB family+port route, not sda or a particular thumb drive. Linux companion peer mapping includes both USB2 and USB3 on the same physical socket. Kernel USB bus renumbering does not affect binding. Other USB sockets and non-storage exhibit equipment are excluded. Move the extension to a hub/different socket only after rebinding; the hub ordered for other equipment need not change this designated direct connection.

Fresh insertion requires an empty observation while the game is RUNNING. Already-present/startup/admission drives must be removed and reinserted after the timer starts. Missing/unknown observations disarm; a recovered present reading never fabricates an insertion. Key modes ignore the USB objective. Maintenance disables objective completion but shows insertion/removal live in its own USB insertion test card. Check/input button uses standard snapshot action; current live USB state is inside the card. Unknown connection state is distinct from empty.

Validation:159Pi tests,17deployment tests and host firmware tests passed; hardware harness verifies D4 high does not change input3. Tests cover preinserted/startup drive, fresh insertion, break-all flow, game restart, non-USB modes, maintenance, unknown input, wrong socket, partitions, dynamic disk names and bus renumbering. Actual Mega compile16428flash/1160RAM. Archive on portal before flash, Pi/Mac copies retained. Live0.22.0 connected; bound socket reports present=true and no errors. Real removal/reinsertion and physical gameplay acceptance pending user.

Current OS desktop had automatically mounted the sample drive before this work. The game itself does not mount, read or execute files. Desktop automount settings were not changed; visitor-port OS hardening remains a separate deployment consideration.

No USB filesystem files inspected. Binding is private runtime configuration, excluded from source archives. User can remove button wiring from D4 with power off after update. Portal backup zoco-portal-private/usb-objective/backup-20261105-205048-c473b3. Prior hardware docs referring to latching objective are historical.

## Physical acceptance confirmed
User removed and reinserted the test drive; live telemetry verified one removal and one insertion without errors. User then ran standard USB mode (RFID +16646#), inserted the drive after the timer started, and confirmed the mission completed.
