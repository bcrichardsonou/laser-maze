"""Button input bench test, not a full game. Stop with Control+C."""
import argparse
import time


def send(port, command):
    port.write((command + "\n").encode("ascii"))
    port.flush()


def expect(port, command, reply):
    send(port, command)
    received = port.readline().decode("ascii", errors="replace").strip()
    if received != reply:
        raise RuntimeError(f"{command}: expected {reply!r}, received {received!r}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version="bench-0.21.0")
    parser.add_argument("port")
    args = parser.parse_args()
    import serial
    import fcntl
    from pathlib import Path
    lock_dir = Path.home() / "laser-maze/deployments"
    lock_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    controller_lock = (lock_dir / "deploy.lock").open("a")
    try:
        fcntl.flock(controller_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        controller_lock.close()
        parser.exit(1, "Another test or deployment is using the controller.\n")
    with controller_lock, serial.Serial(args.port, 115200, timeout=0.05, write_timeout=1) as port:
        time.sleep(2)
        port.reset_input_buffer()
        port.timeout = 2
        try:
            expect(port, "HELLO", "HELLO 1 bench-0.21.0")
            expect(port, "BEAM", "BEAM CLEAR")
            expect(port, "ARM", "OK ARM")
            # Input events may occur between command acknowledgments, so handle
            # all subsequent traffic through one reader.
            send(port, "ON")
            port.timeout = 0.05
            count = 0
            broken = False
            pending = bytearray()
            last_reply = time.monotonic()
            next_heartbeat = 0.0
            print("Press and release the button. Hold it to verify only one break.", flush=True)
            print("Control+C stops the test and turns the LED off.", flush=True)
            while True:
                now = time.monotonic()
                if now - last_reply > 2:
                    raise RuntimeError("Arduino stopped acknowledging heartbeats")
                if now >= next_heartbeat:
                    send(port, "HB")
                    next_heartbeat = now + 0.25
                pending.extend(port.read(port.in_waiting or 1))
                if len(pending) > 4096:
                    raise RuntimeError("Unexpected oversized serial response")
                while b"\n" in pending:
                    raw, _, remainder = pending.partition(b"\n")
                    pending = bytearray(remainder)
                    line = raw.decode("ascii", errors="replace").strip()
                    if line == "OK HB":
                        last_reply = time.monotonic()
                    elif line == "BEAM BROKEN":
                        if not broken:
                            count += 1
                            print(f"Beam broken — count {count}", flush=True)
                        broken = True
                    elif line == "BEAM CLEAR":
                        broken = False
                        print("Beam clear", flush=True)
                    elif line == "OK ON":
                        print("LED output is on", flush=True)
                    elif line:
                        raise RuntimeError(f"Unexpected Arduino response: {line}")
        except KeyboardInterrupt:
            print("\nTest stopped.")
        finally:
            try:
                send(port, "OFF")
            except (serial.SerialException, OSError):
                pass


if __name__ == "__main__":
    main()
