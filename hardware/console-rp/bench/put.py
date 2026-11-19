# Copy files onto a bench console-rp's filesystem through the raw REPL that main_repl.py puts on the
# USB-C's serial port (rawrepl.py runs the copy). Bench only, like main_repl.py.
#
#   uv run --no-project --with pyserial==3.5 python hardware/console-rp/bench/put.py PORT FILE...
#
# Each FILE goes in as /its-name.
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def main(argv):
    port, paths = argv[0], argv[1:]
    for path in paths:
        data = open(path, "rb").read()
        name = os.path.basename(path)
        lines = ["f = open(%r, 'wb')" % name]
        for i in range(0, len(data), 256):
            lines.append("f.write(%r)" % data[i:i + 256])
        lines += ["f.close()", "import os", "print(%r, os.stat(%r)[6])" % (name, name)]
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as t:
            t.write("\n".join(lines) + "\n")
        try:
            subprocess.run([sys.executable, os.path.join(HERE, "rawrepl.py"), port, t.name], check=True)
        finally:
            os.unlink(t.name)


if __name__ == "__main__":
    main(sys.argv[1:])
