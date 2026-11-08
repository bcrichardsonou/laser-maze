# RC522 mission-code entry — bench-0.17.0

## Wiring (power off)
RC5223.3V→Mega3.3V; GND→MegaGND; SDA/SS→D53, SCK→D52, MOSI→D51, RST→D49, each of these four Mega outputs through suitable5V-to3.3V logic conversion. MISO→MegaD50 directly; IRQ unconnected. The SDA label on this SPI board means slave select, NOT I2C SDA20. Keep wires short. Reader13.56MHz ISO14443A compatible cards/tags; other RFID frequencies/protocols will not read. Onboard3.3V is power only; does not level-shift5V GPIO. Retained circuits unaffected: status8pixelsD6, keypad20/21, TM1637D7/8, Nano-commandD9, receiverA0, beam-buttonD3, objectiveD4, indicatorD5. NanoD3MOSFETtrigger/NanoD6ring remain unchanged.

## Mission entry
| Code | Mission | Internal bench mode |
|---|---|---|
|77004#|Corruption Reduction normal|keys|
|40077#|Corruption Reduction accessible|keys-break-all|
|16646#|Black Hat / Vexed normal|usb|
|64661#|Black Hat / Vexed accessible|usb-break-all|

Any successfully read compatible RFID tag + valid six-character code authorize ONE game. No tagUID is transmitted/stored and no allowlist/database authorization is implied. Library1.4.12 uses card read+halt, avoiding repeated events from a held halted tag. Detection events ignored for authorization in preparation/admission/running/maintenance and during post-result occupancy. Cannot override current mode midgame. Readerhealth sampled2seconds, tags100ms whenavailable; missing reader does not crashcontroller or disablemaintenance but blocksnewentry. Auto-reprobe supports reconnect; physicalhotplug not prescribed.

Either order is supported by the game outline. Scan-first: starttyping within5seconds, subsequentcharacters eachwithin5seconds. Code-first: eachcharacterwithin5seconds, scanwithin5secondsafter# (or duringentry). Completed six-character buffer freezes extra input untilscan or timeout. Invalidcode, premature#, timeout, *clear, Dstop, maintenance, readerloss, playlock resetentry. Disabled operator modes rejected. A/manual1–4 start bypass removed in production controller; standalone Controls unit/legacytests opt out explicitly. Dstillstops; C/B maintenance controls preserved. At rest lightred; successful authorization beginsyellowprep→greenadmission→bluecountdown.

This change adds mission selection, not new mission-completion hardware or revised objective rules. Existing bench USB-latch objective and accessiblebreak-all logic retained. The outline explicitly leaves BlackHat/Vexed accessible completion unresolved and says USB objective sensor absent in final installation. That final gameplay decision is still outstanding; code cannot distinguish BlackHat fromVexed because outline assigns identicalcodes. Current normal breaklimit/operator settings retained rather than silently changing othergameplay.

## Diagnostics and verification
Portal maintenance live diagnostics: readerready, scan count, seconds since scan, entry state, count/6 and time remaining; Inputsnapshot includes reader health/count/state. Inmaintenance a swipe updatesdiagnostics only, never startsplay. Console shows boundedentryfeedbackwithoutUID/codecontents. Three extra compactgeneralmetrics keepstatuswithin40keys; detailedentrydatausesfastfeed.
92Pi tests (allcodes/bothorders/timeout/invalid/disabled/bypass/progress-stop),17deploymenttests,1hostfirmwaretest includinghealth/tag/heldcard behavior pass. ActualMega compile14174flash/1041staticRAM. Physicalreaderwiring/cardacceptance remains usertest.

First test: poweroffwire; poweron; maintenance→C; verify readerready, swipecard and scan count rises; Bexit; swipe then77004#; verify yellowprep5s, greenadmission5s, blue150s. Dstop. Testremainingthreecodes; testlate/wrongcodeneverstart; existing laser/calibration/status/rebootchecks retained.

## RFID acknowledgment light — bench-0.17.1
In normal idle operation, an accepted scan turns the separateD6statuslightPURPLE while waitingforcode. It remains purple through validintercharacterentrywindows, returnsREDon timeout/*/D/entrylock, and becomesYELLOWimmediatelywhenmatchingcode+scanstartpreparation. Code-firstcompletedentries startyellowimmediatelyon scan. Scansduringmaintenance/gameplaydo notchangetheirphasecolor. This adds an explicit entry-authorizationcolor to the documentedred/yellow/green/bluesequence. Physicalacceptancepending.

## Band detection investigation — corrected bench-0.17.3
User's MarioBand didnotproduceacceptedscan; supportnotclaimed. SetmaximumsupportedRXgain48dB (gainregister112), noTXpowerincrease, retainType-Arequest/selectstatus. CombinedRFIDhealthreplyincludes responsecount,selectionfailurecount,lastrequeststatus,lastselectionstatus,gain; periodicrequestremainsRFIDalone2s. Avoidextraqueriesinstartupburst: experimental0.17.2DIAGrequestresultedinERRCOMMANDandwasreplacedwith0.17.3. Controlleroutputsdisabledonprotocolfault; serviceexplicitlystoppeduntilcorrectedreleaseverified. Lastrequest3meansrequesttimeout/noresponseonthatpoll; lastselection3initiallyunknown/timeoutuntilselectionattempt. Responsecountcanincreasewithoutacceptedscanifselectionfails. NoUIDsaved. Physicalbandretestandknown-goodcardcomparisonstillrequired.
