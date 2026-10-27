"""One-use RFID + six-character mission entry, using monotonic time.

Any successfully read compatible tag authorizes this exhibit; no UID is stored.
Either order is accepted. Complementary action must begin within five seconds;
subsequent code characters each have a five-second gap limit.
"""
CODES = {'77004#': 'keys', '40077#': 'keys-break-all',
         '16646#': 'usb', '64661#': 'usb-break-all'}
WINDOW = 5.0


class Entry:
    def __init__(self):
        self.reset()

    def reset(self, reason='waiting_for_scan_or_code'):
        self.scanned = False
        self.code = ''
        self.deadline = None
        self.reason = reason

    def tick(self, now):
        if self.deadline is not None and now >= self.deadline:
            self.reset('entry_timed_out')

    def take(self, allowed):
        mode = CODES.get(self.code)
        if self.scanned and mode:
            self.reset('entry_accepted' if mode in allowed else 'mode_disabled')
            return mode if mode in allowed else None
        return None

    def swipe(self, now, allowed):
        self.tick(now)
        self.scanned = True
        if not self.code or len(self.code) == 6:
            self.deadline = now + WINDOW
        self.reason = 'enter_mission_code'
        return self.take(allowed)

    def key(self, key, now, allowed):
        self.tick(now)
        if key == '*':
            self.reset('entry_cancelled')
            return None
        if key not in '0123456789#' or len(self.code) >= 6:
            return None
        self.code += key
        self.deadline = now + WINDOW
        if (key == '#' and len(self.code) != 6) or (len(self.code) == 6 and self.code not in CODES):
            self.reset('invalid_mission_code')
            return None
        if len(self.code) == 6:
            self.reason = 'scan_rfid_to_start'
        else:
            self.reason = 'enter_mission_code'
        return self.take(allowed)

    def status(self, now):
        self.tick(now)
        return dict(state=self.reason, scanned=self.scanned, code_characters=len(self.code),
                    seconds_remaining=max(0, round(self.deadline-now, 1)) if self.deadline is not None else 0)
