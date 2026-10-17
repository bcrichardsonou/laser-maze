"""Durable local reporting only; no network requests or shared SQLite locks."""
import datetime as dt
import json
import os
from pathlib import Path
import tempfile
import time
import uuid


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    data = json.dumps(value, allow_nan=False).encode()
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".write-")
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data); out.flush(); os.fsync(out.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


class Reporting:
    def __init__(self, folder, version, fast):
        self.folder = Path(folder).expanduser()
        self.version, self.fast = version, fast
        self.active = self.folder / "active-game.json"
        self.last_status = None
        self.next_refresh = 0
        self.session = None
        self.games_this_run = self.results_this_run = 0
        if self.active.exists():
            previous = json.loads(self.active.read_text())
            final = previous.get("final") or dict(previous["start"], outcome="interrupted",
                elapsed_seconds=None, break_count=None, timing_unconfirmed=True)
            self.emit("bench_game_result", final, self.result_id(previous["session_id"]))
            self.active.unlink()

    def result_id(self, session):
        return str(uuid.uuid5(uuid.UUID(session), "result"))

    def emit(self, kind, payload, event_id=None):
        event_id = event_id or str(uuid.uuid4())
        path = self.folder / "outbox" / (event_id + ".json")
        # A restart/retry never changes an already durable event's identity/content.
        if path.exists(): return
        event = dict(event_id=event_id, occurred_at=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            kind=kind, payload=payload)
        atomic_json(path, event)

    def begin(self, game, now):
        if self.session is not None:
            self.finish(game, now, "interrupted")
        self.session = str(uuid.uuid4())
        self.started = now
        self.games_this_run += 1
        start = dict(session_id=self.session, bench_prototype=True, fast_demo=self.fast,
            mode=game.mode, configured_beams=game.settings.beam_count,
            enabled_beams=[i+1 for i,v in enumerate(game.enabled) if v],
            excluded_beams=[i+1 for i,v in enumerate(game.enabled) if not v],
            configured_duration_seconds=game.settings.duration, python_version=self.version,
            firmware_version=self.version)
        atomic_json(self.active, dict(session_id=self.session, start=start))
        self.emit("bench_game_started", start, str(uuid.uuid5(uuid.UUID(self.session), "start")))

    def finish(self, game, now, outcome=None):
        if not self.session: return
        record = json.loads(self.active.read_text())
        elapsed = max(0, now - game.running_at) if game.running_at is not None else 0
        final = dict(record["start"], outcome=outcome or game.outcome,
            elapsed_seconds=round(min(elapsed, game.settings.duration), 3),
            break_count=game.breaks, key_progress=game.key_progress,
            objective_completed=game.objective,
            enabled_beams=[i+1 for i,v in enumerate(game.enabled) if v],
            excluded_beams=[i+1 for i,v in enumerate(game.enabled) if not v])
        record["final"] = final
        atomic_json(self.active, record)
        self.emit("bench_game_result", final, self.result_id(self.session))
        self.active.unlink()
        self.session = None
        self.results_this_run += 1

    def status(self, controls, desired, now, connected=True, fault="", stopped=False, audio=None, maintenance=None):
        if not fault and not stopped and controls.result and controls.result[0] in ("startup_blocked", "no_beams_available"):
            fault = controls.result[0]
        game = controls.game
        phase = "fault" if fault else "stopped" if stopped else game.state if game else "finished" if controls.result else "idle"
        metrics = dict(bench_prototype=True, fast_demo=self.fast, game_phase=phase, game_mode=controls.mode,
            arduino_connected=connected, keypad_available=connected, python_version=self.version,
            firmware_version=self.version if connected else "unconfirmed", configured_beams=2,
            remaining_seconds=desired[2], break_count=game.breaks if game else controls.result[1] if controls.result else 0,
            key_progress=game.key_progress if game else 0, objective_completed=game.objective if game else False,
            beam1_input_active=controls.levels[0], beam2_input_active=controls.levels[1], latch_active=controls.levels[2],
            beam1_commanded_on=desired[0], beam2_commanded_on=desired[1], rgb_requested=desired[3],
            bench_games_this_run=self.games_this_run, bench_results_this_run=self.results_this_run)
        enabled = game.enabled if game else getattr(controls, "last_enabled", None)
        if enabled is not None:
            metrics["active_beams"] = sum(enabled)
            metrics["excluded_beams"] = ",".join(str(i+1) for i,v in enumerate(enabled) if not v)
        if self.session: metrics["session_id"] = self.session
        if controls.result: metrics["last_result"] = controls.result[0]
        if audio: metrics.update(audio)
        if maintenance: metrics.update(maintenance)
        if maintenance and (maintenance['maintenance_enabled'] or maintenance['maintenance_pending']) and not fault and not stopped:
            phase='maintenance';metrics['game_phase']=phase
        state = "faulted" if fault else "unknown" if stopped or not connected else "running" if game else "ready"
        if phase=='maintenance' and connected:state='maintenance'
        status = dict(state=state, fault_summary=fault, metrics=metrics)
        signature = json.dumps({k:v for k,v in metrics.items() if k != "remaining_seconds"}, sort_keys=True)
        changed = signature != self.last_status
        if changed or now >= self.next_refresh:
            atomic_json(self.folder / "game-status.json", status)
            if changed:
                self.emit("status", status)
                if fault: self.emit("bench_controller_fault", dict(bench_prototype=True, reason=fault))
            self.next_refresh = now + 10
            self.last_status = signature


def transfer_outbox(folder, config_path, agent_path):
    """Transfer by original UUID into existing agent queue; commit before unlink."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("zoco_existing_agent", agent_path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    agent = module.Agent(str(Path(config_path).expanduser()))
    try:
        for path in sorted((Path(folder).expanduser() / "outbox").glob("*.json"))[:100]:
            event = json.loads(path.read_text())
            if str(uuid.UUID(event["event_id"])) != path.stem: raise ValueError("Outbox identity mismatch")
            if event["kind"] not in ("status", "bench_game_started", "bench_game_result", "bench_controller_fault"):
                raise ValueError("Unexpected outbox event")
            payload = json.dumps(event["payload"], allow_nan=False)
            if len(payload.encode()) > 8192: raise ValueError("Outbox payload too large")
            agent.db.execute('INSERT OR IGNORE INTO events(event_id,occurred_at,kind,payload) VALUES (?,?,?,?)',
                (event["event_id"], event["occurred_at"], event["kind"], payload))
            agent.db.commit()
            path.unlink()
    finally: agent.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Move local game reports into the existing ZoCo upload queue")
    parser.add_argument("--folder", default="~/zoco-monitor/laser-maze")
    parser.add_argument("--config", default="~/zoco-monitor/device-config.json")
    parser.add_argument("--agent", default="~/zoco-monitor/zoco_agent.py")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    while True:
        transfer_outbox(args.folder, args.config, str(Path(args.agent).expanduser()))
        if args.once: break
        time.sleep(1)


if __name__ == "__main__": main()
