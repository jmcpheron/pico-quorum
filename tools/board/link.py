# The laptop's end of the USB link (firmware/usblink.py, docs/USB-LINK.md): one request to the
# console on PORT, its answer printed as one line of JSON. tools/board/fw.mjs runs it as
#   uv run --no-project --with pyserial==3.5 python tools/board/link.py PORT '{"op": "hello"}' [WAIT_S]
# Exit 0 with the answer; 2 when nothing answered in WAIT_S (an older image, maintenance's REPL, a
# board still starting); 1 when the port could not be opened.
#
# DTR and RTS stay low, before the port opens and after: on an ESP32-S3's own USB, their edges reset
# the chip or start its ROM bootloader. Nothing here sends Ctrl-C, and the request is one line.
import json
import sys
import time

import serial


def main():
    port, req = sys.argv[1], json.loads(sys.argv[2])
    wait = float(sys.argv[3]) if len(sys.argv) > 3 else 3
    req.setdefault("id", int(time.time() * 1000) % 1000000000)
    s = serial.Serial()
    s.port, s.baudrate, s.timeout = port, 115200, 0.1
    s.dtr = s.rts = False
    try:
        s.open()
    except (OSError, serial.SerialException) as e:
        print(json.dumps({"error": str(e)}))
        return 1
    try:
        s.reset_input_buffer()
        s.write((json.dumps(req) + "\n").encode())
        s.flush()
        buf, end = b"", time.time() + wait
        while time.time() < end:
            buf += s.read(4096)
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line.startswith(b'{"pq":'):
                    continue            # the console's own prints
                try:
                    a = json.loads(line)
                except ValueError:
                    continue
                if a.get("id") == req["id"]:
                    print(json.dumps(a))
                    return 0
        return 2
    finally:
        try:
            s.close()
        except (OSError, serial.SerialException):
            pass


if __name__ == "__main__":
    sys.exit(main())
