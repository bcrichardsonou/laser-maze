"""Wired input diagnostic. No game starts; Control+C stops and turns lights off."""
import argparse
from collections import deque
import fcntl
from pathlib import Path
import time

VERSION = "bench-0.12.0"
LABELS = ("Beam button 1 (D2)", "Beam button 2 (D3)", "USB objective latch (D4)")


def describe(line):
    parts = line.split()
    if len(parts) == 3 and parts[0] == "INPUT" and parts[1] in ("0", "1", "2") and parts[2] in ("0", "1"):
        return f"{LABELS[int(parts[1])]}: {'ACTIVE' if parts[2] == '1' else 'released'}"
    if len(parts) == 4 and parts[0] == "INPUTS" and all(p in ("0", "1") for p in parts[1:]):
        return " | ".join(f"{label}: {'ACTIVE' if p == '1' else 'released'}" for label, p in zip(LABELS, parts[1:]))
    if line == "KEY UP": return "Key released"
    if line == "KEY INVALID": return "Multiple/invalid keys — press one key at a time"
    if len(parts) == 2 and parts[0] == "KEY" and parts[1] in "0123456789ABCD*#" and len(parts[1]) == 1:
        return f"Key pressed: {parts[1]}"
    raise RuntimeError(f"Unexpected input message: {line}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("port")
    args = parser.parse_args()
    import serial
    directory = Path.home() / "laser-maze/deployments"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = (directory / "deploy.lock").open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        parser.exit(1, "Stop the other controller test first.\n")
    with lock, serial.Serial(args.port, 115200, timeout=2, write_timeout=1) as port:
        def exchange(command, expected):
            port.write((command + "\n").encode())
            port.flush()
            line = port.readline().decode("ascii", errors="replace").strip()
            if line != expected:
                raise RuntimeError(f"{command}: expected {expected}, received {line}")

        def hold(seconds):
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                exchange("HB", "OK HB")
                time.sleep(0.2)

        try:
            time.sleep(2)
            port.reset_input_buffer()
            exchange("HELLO", "HELLO 1 bench-0.12.0")
            exchange("KEYPAD", "KEYPAD READY")
            exchange("ARM", "OK ARM")
            print("Panel diagnostic. The simulated laser stays OFF.", flush=True)
            exchange("LED ON", "OK LED ON")
            print("D5 indicator should be ON.", flush=True)
            hold(1)
            exchange("LED OFF", "OK LED OFF")
            for color in ("RED", "GREEN", "BLUE"):
                exchange("RGB " + color, "OK RGB " + color)
                print("RGB pixel should be " + color, flush=True)
                hold(1)
            exchange("RGB OFF", "OK RGB OFF")
            exchange("DISPLAY TEST", "OK DISPLAY TEST")
            print("TK51 should show 88:88, with all digits and colon lit.", flush=True)
            hold(1)
            for seconds in (150, 149, 148, 5, 4, 3, 2, 1, 0):
                exchange(f"TIME {seconds}", "OK TIME")
                print(f"TK51 should show {seconds // 60:02d}:{seconds % 60:02d}", flush=True)
                hold(1)
            exchange("PANEL", "OK PANEL")
            port.timeout = 0.03
            pending = bytearray()
            replies = deque()
            next_heartbeat = next_snapshot = 0
            snapshot = None
            print("Press/release both buttons, toggle the latch, then test every keypad key.", flush=True)
            print("Hold a key: it should report once. Control+C stops and turns lights off.", flush=True)
            while True:
                now = time.monotonic()
                pending.extend(port.read(port.in_waiting or 1))
                if len(pending) > 4096:
                    raise RuntimeError("Oversized serial message")
                while b"\n" in pending:
                    raw, _, pending = pending.partition(b"\n")
                    line = raw.decode("ascii", errors="replace").strip()
                    if line == "OK HB" and replies and replies[0][0] == "HB":
                        replies.popleft()
                    elif line.startswith("INPUTS "):
                        message = describe(line)
                        if line != snapshot:
                            print(message, flush=True)
                            snapshot = line
                        if replies and replies[0][0] == "INPUTS": replies.popleft()
                    elif line.startswith("INPUT ") or line.startswith("KEY "):
                        print(describe(line), flush=True)
                    elif line:
                        raise RuntimeError(f"Controller fault/unexpected reply: {line}")
                if replies and now > replies[0][1]:
                    raise RuntimeError("Controller acknowledgment timed out")
                for text, due in (("HB", next_heartbeat), ("INPUTS", next_snapshot)):
                    if now >= due:
                        port.write((text + "\n").encode())
                        port.flush()
                        replies.append((text, now + 1))
                        if text == "HB": next_heartbeat = now + 0.25
                        else: next_snapshot = now + 0.5
        except KeyboardInterrupt:
            print("\nPanel test stopped.", flush=True)
        except (OSError, RuntimeError, serial.SerialException) as error:
            parser.exit(1, f"Panel test failed: {error}\n")
        finally:
            try:
                port.write(b"OFF\n")
                port.flush()
            except (OSError, serial.SerialException):
                pass


if __name__ == "__main__":
    main()
