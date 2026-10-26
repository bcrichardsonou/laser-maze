"""Hardware-independent Laser Maze rules, driven by monotonic seconds."""
from dataclasses import dataclass
import math

MODES = ("usb", "usb-break-all", "keys", "keys-break-all")


@dataclass(frozen=True)
class Settings:
    beam_count: int = 1
    startup: float = 5
    duration: float = 150
    cooldown: float = 7
    warmup: float = 5
    max_breaks: int = 3
    enabled_beams: tuple = ()

    def __post_init__(self):
        if not isinstance(self.beam_count, int) or not 1 <= self.beam_count <= 32:
            raise ValueError("Beam count must be 1–32")
        if self.enabled_beams and (len(self.enabled_beams)!=self.beam_count or any(type(v) is not bool for v in self.enabled_beams) or not any(self.enabled_beams)):
            raise ValueError("Invalid enabled beams")
        if not isinstance(self.max_breaks, int) or self.max_breaks < 1:
            raise ValueError("Break limit must be positive")
        for value in (self.startup, self.duration, self.cooldown, self.warmup):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Timing settings must be finite and positive")


class Game:
    KEY_ORDER = (1, 3, 2, 4)

    def __init__(self, mode="usb", settings=None, powered_startup=False):
        if mode not in MODES:
            raise ValueError("Unknown game mode")
        self.mode = mode
        self.powered_startup = powered_startup
        self.settings = settings or Settings()
        self.state = "idle"
        self.outcome = None
        self.breaks = 0
        self.key_progress = 0
        self.objective = False
        self.broken = [False] * self.settings.beam_count
        self.enabled = [True] * self.settings.beam_count
        self.completed = [False] * self.settings.beam_count
        self.reenable_at = [None] * self.settings.beam_count
        self.monitor_at = [None] * self.settings.beam_count
        self.running_at = None
        self.deadline = None

    @property
    def break_all(self):
        return self.mode.endswith("break-all")

    def start(self, now):
        if self.state != "idle":
            raise ValueError("Create a new game to restart")
        self.enabled = [configured and (self.powered_startup or not broken) for configured,broken in zip(self.settings.enabled_beams or [True]*self.settings.beam_count,self.broken)]
        if not any(self.enabled):
            self.finish("no_beams_available", fault=True)
            return
        self.state = "starting"
        self.running_at = now + self.settings.startup
        self.deadline = self.running_at + self.settings.duration

    def finish(self, outcome, fault=False):
        self.outcome = outcome
        self.state = "fault" if fault else "finished"

    def beam(self, index, broken, now):
        if not 0 <= index < self.settings.beam_count:
            raise ValueError("Unknown beam")
        self.broken[index] = bool(broken)
        self.tick(now)

    def objective_usb(self, now):
        self.tick(now)
        if self.state == "running" and self.mode.startswith("usb"):
            self.objective = True
            self.check_win()

    def key(self, number, now):
        self.tick(now)
        if self.state != "running" or not self.mode.startswith("keys") or self.objective:
            return
        if number == self.KEY_ORDER[self.key_progress]:
            self.key_progress += 1
            self.objective = self.key_progress == len(self.KEY_ORDER)
            self.check_win()

    def check_win(self):
        if self.objective and (not self.break_all or all(not enabled or done for enabled, done in zip(self.enabled, self.completed))):
            self.finish("win")

    def tick(self, now):
        if self.state == "starting" and now >= self.running_at:
            self.enabled = [enabled and not broken for enabled, broken in zip(self.enabled, self.broken)]
            if not any(self.enabled):
                self.finish("no_beams_available", fault=True)
                return
            self.state = "running"
        if self.state != "running":
            return
        if now >= self.deadline:
            self.finish("timeout")
            return
        for i, broken in enumerate(self.broken):
            if not self.enabled[i] or self.completed[i] or (self.monitor_at[i] is not None and now < self.monitor_at[i]):
                continue
            if broken:
                self.breaks += 1
                if self.break_all:
                    self.completed[i] = True
                    self.check_win()
                elif self.breaks >= self.settings.max_breaks:
                    self.finish("beam_limit")
                else:
                    self.reenable_at[i] = now + self.settings.cooldown
                    self.monitor_at[i] = self.reenable_at[i] + self.settings.warmup
                if self.state != "running":
                    return

    def outputs(self, now):
        if self.state == "starting" and self.powered_startup:
            return tuple(self.enabled)
        if self.state != "running":
            return (False,) * self.settings.beam_count
        return tuple(self.enabled[i] and not self.completed[i] and (self.reenable_at[i] is None or now >= self.reenable_at[i])
            for i in range(self.settings.beam_count))

    def remaining(self, now):
        if self.running_at is None:
            return self.settings.duration
        return max(0, self.deadline - max(now, self.running_at))
