# Hazer / DMX — installed mega-hazer-dmx-0.25.0

November7,2026. User ordered analog multiplexer (not connected/implemented yet), plugged DSD TECH SH-RS09B USB-DMX; confirmed no receiving fixture/hazer connected. Detected FTDI0403:6001, stable port /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_EXAMPLE_DMX_SERIAL-if00-port0. Runtime private control/dmx-settings.json: address10, automaticfalse, pump16/fan64 rawDMX,11s burst. Config excluded from archive. Actual machine must be set to010 (pump10/fan11); use UNIQUE2.1 five-pin DMX, not its three-pin analog connector.

## Output and tests

hazer_dmx.py isolated process sends513-byte rawDMX universe (startcode0 plus512slots),250000baud/8N2,200us minimum programmedbreak and20us programmedmark-after-break, nominal30Hz. Actual timing on wire not scoped; scheduling and USB latency not assumed zero. Other slots zero. Parent writes nonblocking leases; worker forces pump/fan zero when lease expires (~0.7s), sends3zero frames on graceful EOF, reconnects stableport; same active game/test blocked after observed connection fault to avoid surprise resumption. USB/DMX loss behavior of receiving machine follows its own controller; this is not a hardwired emergency stop.

Portal Hazer/DMX shortcut: live adapter/transmit/frame/rawoutput status; zero-only5s adapter check; fan-only5s; configurable1–10s haze test; Stop haze disables futureauto and requestszeros; EndDMXsignal for machine post-run; ResumezeroDMX; settings address1–511/pumpfan0–255/burst1–30/automaticcheckbox. Tests/settings/resume need maintenance+local5; stop/pause bypasslocalgrant and pendingtestblocks. One-wayDMX cannot prove physical response, heater ready, fluid level or cooldown completion. Keep actualhazer mains powered until manufacturer's cooldown complete.

AutomaticgamehazeOFF until physical commissioning. When explicitly enabled, starts once at preparation, defaults11s (maycontinue throughadmission/earlyplay), stops atdeadline or gameend. State handling separatefromMegaUART/audio/sensors; ten-secondexit/RFID/USBmission unchanged.

## Validation/deployment

181Pi tests,17release tests,firmwarehost harness; workerfakeUART leaseexpiry/EOF/format, framebounds and settings/inputvalidation, oneburst/session, testexpiry/cancel, full6000bytepayload bound. Actualadapter software test81zeroframes; installedlive subsequently1969frames/noerror/pump0fan0/autofalse, bothversionsbench0.25.0, allfourservicesactive/RFIDready/doorsHIGHHIGH. No positive pump/fan output or remotegame/maintenancegrant triggered by agent. Physicalhazer/cable/DMXwaveform/warmup/output-level/stop/cooldown/reboot/reconnectacceptance pending.

Portal60checks/PHP/JSsyntax/read-onlyinstalledrender/layoutpass. Privatebackup hazer-dmx/backup-20261107-102144-5a2ab5. Screenshot installed-controls.png uses installedexcerpt with forms disabled, classes preserved.

Initialarchive rejectedHTTP400 because41trackedfiles exceeded40-filevalidator; flash not started; serviceleftstopped. User explicitly approved boundedlimit64 afterautoreviewrequest. Guarded release-lib.php update tested64accept/65reject/pathtraversalreject;8MB/checksum/auth/pathchecks unchanged. Backup hazer-dmx/release-lib.backup-20261107-102447.php. Retriedexactunchangedsavedarchive afterfix, archivedbeforeflash, verifiedhandshake/currentlink; explicitlyrestartedgamebecausepreviousfailurehadleftitstopped. Maintenancebridge refreshed sameUIDverifiedSIGTERM/systemdRestartalways for newactionallowlist. Macarchive retained.

Release tracks41files:7Arduino/Nano,16Python,11audio/provenance,3tools,4compiled. Plus manifest inventory in tarball. This is a complete immutable Pi/MCU software snapshot, not41changedfiles. Portalcode/privateconfiguration not bundled; portalbackup separate; no credentials in archive.

## Sources

Manufactureradapter: https://www.deshide.com/product-details_SH-RS09B.html
Hazeroperatingmanual: https://www.looksolutions.com/uploads/pdf/en_fr/bed_unique21_1e.pdf
PySerialAPI: https://pyserial.readthedocs.io/en/latest/pyserial_api.html
