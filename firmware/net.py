# WiFi plus an optional network console for isolated development.
# The console is passwordless arbitrary code execution and must remain disabled when holding value.
import network, socket, os, time
from machine import Pin
import wificfg
try:
    import secrets
except ImportError:
    secrets = None      # a board without secrets.py: WiFi from wifi.json only, no console

led = Pin("LED", Pin.OUT)
PORT = 2323
_listen = None
tried = False       # connect() ran once (boot.py); wallet.start does not wait a second time
last_try = 0        # ticks_ms of the last join attempt; wallet.net_work retries every 30 s without blocking
up = False          # joined() ran: LED on, console started if wanted
_cur = None         # the (ssid, password) joined or being joined
_turn = 0           # retry() walks the saved networks in turn


def networks():
    """Every network this board knows, newest first: those set up on the Wi-Fi setup screen
    (wifi.json, wifisetup.py), then secrets.py's WIFI_SSID. None at all: boot.py opens setup."""
    out = wificfg.load()
    s = getattr(secrets, "WIFI_SSID", "") if secrets else ""
    if s and s != "your-ssid" and all(n[0] != s for n in out):
        out.append((s, getattr(secrets, "WIFI_PASS", "")))
    return out


def ssid():
    """The network joined or being joined, else the first one known, else ""."""
    n = _cur or (networks() or [("", "")])[0]
    return n[0]


def _hostname():
    return getattr(secrets, "HOSTNAME", "picoquorum") if secrets else "picoquorum"


def _pick(wlan, nets):
    """With several networks known, the first that is in range (one scan, about 2 s)."""
    if len(nets) == 1:
        return nets[0]
    try:
        near = set(s[0].decode() for s in wlan.scan())
        for n in nets:
            if n[0] in near:
                return n
    except Exception as e:
        print("wifi scan:", e)
    return nets[0]


def connect(timeout_s=12, progress=None):
    """Join a known WiFi (networks()), waiting at most timeout_s. progress(elapsed_ms), if given, is called
    while waiting (the boot screen animates on it) and may return True to stop waiting (a key press);
    the LED blinks either way. A network that is not there costs 12 s once, never more: the wallet
    retries in the background (retry) and everything local works without it."""
    global tried, last_try, _cur
    tried = True
    last_try = time.ticks_ms()
    wlan = network.WLAN(network.STA_IF)
    nets = networks()
    if not nets:
        print("no WiFi saved: not joining")
        return wlan
    network.hostname(_hostname())
    wlan.active(True)
    if not wlan.isconnected():
        _cur = _pick(wlan, nets)
        wlan.connect(*_cur)
        t0 = time.ticks_ms()
        while not wlan.isconnected() and time.ticks_diff(time.ticks_ms(), t0) < timeout_s * 1000:
            led.toggle()
            if progress:
                try:
                    if progress(time.ticks_diff(time.ticks_ms(), t0)):
                        print("wifi: wait skipped")
                        break
                except Exception:
                    pass
            time.sleep_ms(150)
    if wlan.isconnected():
        led.on()
        print("wifi up:", wlan.ifconfig()[0], "hostname:", _hostname())
    else:
        led.off()
        print("wifi failed, status", wlan.status())
    return wlan


def retry():
    """Ask the radio to join again and return at once; isconnected() says later whether it did.
    With several networks known, each retry tries the next one."""
    global last_try, up, _cur, _turn
    last_try = time.ticks_ms()
    up = False
    nets = networks()
    if not nets:
        return
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        _turn += 1
        _cur = nets[_turn % len(nets)]
        try:
            wlan.connect(*_cur)
        except OSError as e:
            print("wifi retry:", e)


def joined():
    """Call once the network is up (boot, or a later retry): LED on, the console if secrets.py wants it.
    Never on the production console image: that console is a passwordless REPL that can sign."""
    global up
    up = True
    led.on()
    import image
    if _listen is None and getattr(secrets, "ENABLE_NETWORK_CONSOLE", False) and not image.PRODUCTION:
        console()


def _accept(ls):
    try:
        conn, addr = ls.accept()
    except OSError:
        return  # nothing pending (non-blocking listen socket)
    print("console from", addr)
    conn.setblocking(False)
    os.dupterm(conn, 0)


def short_err(e):
    """A network error in the width of one status row: the usual OSErrors by name, the rest as repr."""
    a = getattr(e, "args", ())
    if isinstance(e, ValueError) and "verif" in str(e).lower():
        return "certificate rejected"       # mbedTLS refused the server's certificate (vhttp.py)
    if isinstance(e, OSError) and a and isinstance(a[0], int):
        return {-2: "dns: host not found", 104: "connection reset", 110: "timed out",
                111: "connection refused", 113: "host unreachable"}.get(a[0], "OSError %d" % a[0])
    return repr(e)[:23]


def poll_accept():
    """Call from a timer tick. The socket-accept callback needs a free scheduler slot, which a busy
    timer can starve; polling here means a connection can never get stuck in the backlog."""
    if _listen:
        _accept(_listen)


def console(port=PORT):
    global _listen
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(socket.getaddrinfo("0.0.0.0", port)[0][-1])
    s.listen(2)
    s.setblocking(False)
    s.setsockopt(socket.SOL_SOCKET, 20, _accept)  # 20 = register accept callback
    _listen = s
    print("console listening on", port)


def start(progress=None):
    wlan = connect(progress=progress)
    if wlan.isconnected():
        joined()
        if _listen is None:
            print("network console disabled")
    return wlan
