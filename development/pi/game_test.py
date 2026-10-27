"""One-beam terminal game test. USB/key objectives are keyboard simulations."""
import argparse
from collections import deque
import fcntl
import math
from pathlib import Path
import select
import sys
import time

from game_engine import Game, Settings, MODES

VERSION = "bench-0.17.2"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("port")
    parser.add_argument("--mode", choices=MODES, default="usb")
    parser.add_argument("--fast", action="store_true", help="Bench demo: 2s startup, 30s game, 2s recovery + 1s warmup")
    args = parser.parse_args()
    import serial
    state_dir = Path.home() / "laser-maze/deployments"
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = (state_dir / "deploy.lock").open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        parser.exit(1, "Stop the other controller test/deployment first.\n")
    settings = Settings(startup=2, duration=30, cooldown=2, warmup=1) if args.fast else Settings()
    game = Game(args.mode, settings)
    acknowledgments = deque()
    pending = bytearray()
    shown = None
    output = None
    displayed_seconds = None
    with lock, serial.Serial(args.port, 115200, timeout=0.02, write_timeout=1) as port:
        def command(text, expected):
            port.write((text + "\n").encode())
            port.flush()
            acknowledgments.append((expected, time.monotonic() + 1))

        def initial(text, expected):
            port.write((text + "\n").encode())
            port.flush()
            reply = port.readline().decode("ascii", errors="replace").strip()
            if reply != expected:
                raise RuntimeError(f"{text}: expected {expected}, received {reply}")

        try:
            time.sleep(2)
            port.reset_input_buffer()
            port.timeout = 2
            initial("HELLO", "HELLO 1 bench-0.17.2")
            initial("BEAM", "BEAM CLEAR")
            initial("ARM", "OK ARM")
            port.timeout = 0.02
            game.start(time.monotonic())
            print(f"ONE-BEAM BENCH GAME — {args.mode}; {'FAST DEMO' if args.fast else 'legacy timings'}", flush=True)
            print("Button = beam. Type u + Enter for USB objective; 1–4 + Enter for keys.", flush=True)
            print("q + Enter or Control+C stops. LED represents the laser, not a fault lamp.", flush=True)
            next_heartbeat = next_poll = 0
            while game.state not in ("finished", "fault"):
                now = time.monotonic()
                # Process incoming beam state before evaluating deadlines.
                pending.extend(port.read(port.in_waiting or 1))
                if len(pending) > 4096:
                    raise RuntimeError("Oversized Arduino response")
                while b"\n" in pending:
                    raw, _, pending = pending.partition(b"\n")
                    line = raw.decode("ascii", errors="replace").strip()
                    if line.startswith("BEAM "):
                        if line not in ("BEAM BROKEN", "BEAM CLEAR"):
                            raise RuntimeError("Unknown beam response")
                        game.beam(0, line == "BEAM BROKEN", now)
                        if acknowledgments and acknowledgments[0][0] == "BEAM":
                            acknowledgments.popleft()
                    elif acknowledgments and line == acknowledgments[0][0]:
                        acknowledgments.popleft()
                    elif line:
                        raise RuntimeError(f"Unexpected controller response: {line}")
                if acknowledgments and now >= acknowledgments[0][1]:
                    raise RuntimeError("Arduino command acknowledgment timed out")
                if game.state in ("finished", "fault"):
                    break
                if select.select([sys.stdin], [], [], 0)[0]:
                    text = sys.stdin.readline()
                    if not text:
                        game.finish("stopped")
                    else:
                        text = text.strip().lower()
                        if text == "q": game.finish("stopped")
                        elif text == "u": game.objective_usb(now)
                        elif text in ("1", "2", "3", "4"): game.key(int(text), now)
                        else: print("Use u, 1–4, or q, then Enter.", flush=True)
                game.tick(now)
                if game.state in ("finished", "fault"):
                    break
                if now >= next_heartbeat:
                    command("HB", "OK HB")
                    next_heartbeat = now + 0.25
                if now >= next_poll:
                    command("BEAM", "BEAM")
                    next_poll = now + 0.25
                desired = game.outputs(now)[0]
                seconds = math.ceil(game.remaining(now))
                if seconds != displayed_seconds:
                    command(f"TIME {seconds}", "OK TIME")
                    displayed_seconds = seconds
                if desired != output:
                    command("ON" if desired else "PAUSE", "OK ON" if desired else "OK PAUSE")
                    output = desired
                # One-beam preview only: no RFID/physical objective/door/hazer integration.
                snapshot = (game.state, math.ceil(game.remaining(now)), game.breaks,
                    game.key_progress, game.objective, desired)
                if snapshot != shown:
                    print(f"{game.state.upper()} | {snapshot[1]}s remaining | breaks {game.breaks}/3 | "
                        f"LED {'on' if desired else 'off'} | objective {'done' if game.objective else 'pending'} | keys {game.key_progress}/4", flush=True)
                    shown = snapshot
            print(f"RESULT: {game.outcome} | total breaks {game.breaks}", flush=True)
        except KeyboardInterrupt:
            game.finish("stopped")
            print("\nRESULT: stopped", flush=True)
        except (OSError, RuntimeError, serial.SerialException) as error:
            game.finish("communication_fault", fault=True)
            parser.exit(1, f"FAULT: {error}\n")
        finally:
            try:
                port.write(b"OFF\n")
                port.flush()
            except (OSError, serial.SerialException):
                pass


if __name__ == "__main__":
    main()
