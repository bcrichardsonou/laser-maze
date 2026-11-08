# ACS ACR1552U integration — installed 0.24.1

Installed November6,2026. New hub05e3:0610 and reader072f:2303 detected. Audio and reader on hub; Mega stable by-id unchanged; visitor USB objective remains original direct Pi socket (controller xhci-hcd.1, USB2/3 route1). Do not relocate visitor extension without rebinding.

## Reader behavior

Actual physical reader exposed by libccid1.6.2/pcscd2.3.3; python3-pyscard2.2.2. User installed prerequisites and enabled pcscd.socket. Explicit user approval obtained for persistent /etc/polkit-1/rules.d/49-zoco-acr1552.rules: existing brent account may access PCSC daemon, card access scoped to reader name containing ACR1552. Initial automatic review rejected unapproved persistent scope; no change occurred until explicit user approval, after which exact rule installed.

Game uses usb_rfid.py child process, with bounded nonblocking parent reads and stale-event/worker-health checks. Select unique ACR1552 PICC interface, excluding SAM; no reader-list index dependency. Multiple matching readers fail closed. Polls PCSC status changes and connects a compatible card, without APDU memory/UID reads or card logging. Initial held card/reconnect requires empty observation before a fresh presentation; held card counts once. Worker handles disconnect/service failure/reconnect; new entry resets on loss, ongoing game not stopped merely for reader loss. USB scans feed existing RFID-plus-code entry or maintenance-only counters. Retired Mega RC522 serial events cannot authorize. Legacy firmware support remains compiled but no Pi RFID health/scan requests used. Old SPI pins are still initialized by legacy firmware; don't assign them anew until firmware cleanup.

## Silent scans

User explicitly approved temporary enabling of vendor escape controls solely for ACR1552 UI configuration and restoring restrictions afterward. Official ACS reference downloaded from https://www.acs.com.hk/download-manual/13473/REF-ACR1552U-Series-1.06.pdf (document content now version1.09, pages90–91). Linux libccid advertises its escape control through PCSC feature request3400/tag0x13; vendor's3500 example alone was unsupported. Temporary ifdDriverOptions0x0001; GetUI E0 00 00 21 00 returned0x2f; SetUI E0 00 00 21 01 27 acknowledged; GetUI verified0x27. Only presence/removal beep bits3/4 cleared; other LED/powerup settings preserved. Original exact driver bytes and ifdDriverOptions0x0000 restored in finally. A plug-in/powerup beep may remain. Persistence through physical unplug/replug and acoustic acceptance still require user check. No persistent vendor-command permission added.

## Deployment/evidence

Archived before flash mega-usb-rfid-0.24.0 then0.24.1 to correct connected-reader entry prompt; both immutable archives copied Mac. Current firmware/Pythonbench0.24.1, Mega16712flash/1205RAM.173Pi tests,17release tests,hostfirmware harness,actualcompile/upload/handshake passed. Portal50checks/PHP/JSsyntax/read-onlyadminrender pass; guardedbackup usb-rfid/backup-20261106-185742-d6113e. Screenshot installed-card.png is read-only excerpt (controls disabled in fixture).

Allfourexhibitservices pluspcscd.socket active. Finalreal live: readerreadytrue/sourceusb_pcsc,1scan/0failures,game_in_progress. No game/card presentation triggered by agent; user scan observed through live telemetry. VisitorUSBconfiguredtrue/errorblank, doors HIGH/HIGH, 10s exit setting retained. Physical gameplaycompletion/reboot/replug/silent-scan/audio acceptance remain user checks. Portal RFID card now describes PiUSB and Reconnectreader, all test readings stay within card.

User physical acceptance, November6: “that worked and the beep is disabled!” New reader operation and acoustic silent scanning confirmed. Reboot/unplug persistence not yet confirmed.

November 6, 2026 — User physically confirmed their Disney wristband works with the ACS ACR1552U on installed release mega-usb-rfid-0.24.1. Compatibility confirmed for that tested wristband; exact Disney band model is not recorded.
