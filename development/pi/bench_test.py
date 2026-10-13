"""Bench LED test only. Requires pyserial. Does not drive installation hardware."""
import argparse
import time
import serial


def exchange(port, command, expected):
    port.write((command + "\n").encode("ascii"))
    port.flush()
    response = port.readline().decode("ascii", errors="replace").strip()
    if response != expected:
        raise RuntimeError(f"{command}: expected {expected!r}, received {response!r}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("port", help="Arduino serial device, preferably /dev/serial/by-id/...")
    args = parser.parse_args()
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
    with controller_lock, serial.Serial(args.port, 115200, timeout=2, write_timeout=2) as port:
        time.sleep(2)
        port.reset_input_buffer()
        try:
            exchange(port, "HELLO", "HELLO 1 bench-0.5.0")
            print("Firmware verified. Turning LED on for five seconds.", flush=True)
            exchange(port, "ARM", "OK ARM")
            exchange(port, "ON", "OK ON")
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                exchange(port, "HB", "OK HB")
                time.sleep(0.25)
            print("Stopping heartbeats. LED should turn off within one second.", flush=True)
            time.sleep(1.5)
            fault = port.readline().decode("ascii", errors="replace").strip()
            if fault != "FAULT WATCHDOG":
                raise RuntimeError(f"Expected watchdog fault, received {fault!r}")
            exchange(port, "STATUS", "STATUS DISARMED OFF")
            print("PASS: firmware reports watchdog shutdown and disarmed output.")
            print("Confirm you also observed the LED turn off.")
        finally:
            # Best effort; the independent Arduino watchdog handles loss of USB.
            try:
                port.write(b"OFF\n")
                port.flush()
            except serial.SerialException:
                pass


if __name__ == "__main__":
    main()
