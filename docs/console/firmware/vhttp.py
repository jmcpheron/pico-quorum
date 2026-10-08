# HTTPS for the console with the server's certificate checked. MicroPython's `requests` turns
# certificate checks off (verify_mode CERT_NONE), so on the board it would hand the API key to
# anyone who answered for api.safe.global. Here the TLS context requires a chain to one of the
# pinned roots (ca_*.bin, DER), the hostname is checked through SNI, and nothing is written, the
# Authorization header included, until the handshake has succeeded.
#
# Pinned roots, the ones api.safe.global's chain ends in (checked 2026-09-26: its certificate <-
# Amazon RSA 2048 M04 <- Amazon Root CA 1, which is also cross-signed by Starfield G2), plus
# Amazon's ECDSA root in case the service moves to an ECDSA certificate:
#   ca_amazon_root1.bin   8ecde688...98196e   (valid to 2038)
#   ca_amazon_root3.bin   18ce6cfe...6db3a4   (valid to 2040)
#   ca_starfield_g2.bin   568d6905...3edab5   (valid to 2037)
# mbedTLS on the Pico checks certificate dates against the clock, so the clock has to be set
# (clock(), NTP) before the first call.
#
#   ctx = context()
#   r = request("GET", "https://api.safe.global/...", headers={...}, ctx=ctx)
#   r.status_code, r.json(), r.close()
import socket
import time
import json as _json
import board

CA_FILES = ("ca_amazon_root1.bin", "ca_amazon_root3.bin", "ca_starfield_g2.bin")
MAX_BODY = 48 * 1024
MIN_YEAR = 2026


def context(files=CA_FILES):
    """One TLS client context with the pinned roots. Build it once, early, while the heap is whole."""
    import tls
    ctx = tls.SSLContext(tls.PROTOCOL_TLS_CLIENT)
    ctx.verify_mode = tls.CERT_REQUIRED
    for f in files:
        with open(f, "rb") as fh:
            ctx.load_verify_locations(fh.read())   # positional: tls's C method takes no keywords; each call adds to the chain
    return ctx


def clock(floor=0):
    """Set the clock from NTP unless it already looks right. Raises OSError if it cannot be set:
    without a clock every certificate looks not yet valid. floor: the build's date, so an answer
    from before the firmware was built (an attacker on the network rolling it back) is refused."""
    if time.gmtime()[0] >= MIN_YEAR and board.unix() >= floor:
        return
    import ntptime
    ntptime.settime()
    if time.gmtime()[0] < MIN_YEAR or board.unix() < floor:
        raise OSError("clock not set (NTP)")


class Response:
    def __init__(self, status, body):
        self.status_code = status
        self.content = body

    def json(self):
        return _json.loads(self.content)

    def close(self):
        pass


def request(method, url, ctx, body=None, headers=None, timeout=15, max_body=MAX_BODY, budget_ms=40000, into=None):
    """timeout applies to each socket operation; budget_ms to the whole response after the
    handshake (the caller's watchdog allowance is budget + the handshake's own timeouts). A body over
    max_body raises MemoryError, as running out of room would: the console then asks for less.
    into: a bytearray the body is read into, in place: the body is then a memoryview of it and needs
    no room of its own while the connection is open (txservice.py says why that matters)."""
    t0 = time.ticks_ms()
    proto, _, host, path = url.split("/", 3)
    if proto != "https:":
        raise ValueError("vhttp is HTTPS only")
    port = 443
    if ":" in host:
        host, port = host.split(":", 1)
        port = int(port)
    ai = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)[0]
    s = socket.socket(ai[0], socket.SOCK_STREAM, ai[2])
    try:
        s.settimeout(timeout)
        s.connect(ai[-1])
        s = ctx.wrap_socket(s, server_hostname=host)     # the handshake: raises unless the chain and name check out
        data = _json.dumps(body).encode() if body is not None else b""
        head = "%s /%s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\nUser-Agent: picoquorum\r\nAccept: application/json\r\n" % (method, path, host)
        for k, v in (headers or {}).items():
            head += "%s: %s\r\n" % (k, v)
        if body is not None:
            head += "Content-Type: application/json\r\nContent-Length: %d\r\n" % len(data)
        s.write(head.encode() + b"\r\n" + data)
        status = int(s.readline().split(None, 2)[1])
        length, chunked = None, False
        while True:
            line = s.readline()
            if not line or line == b"\r\n":
                break
            k, _, v = line.decode().partition(":")
            k = k.strip().lower()
            if k == "content-length":
                length = int(v)
            elif k == "transfer-encoding" and "chunked" in v.lower():
                chunked = True
        if into is not None:
            out = _chunked_into(s, into, t0, budget_ms) if chunked else _plain_into(s, length, into, t0, budget_ms)
        else:
            out = _chunked(s, max_body, t0, budget_ms) if chunked else _plain(s, length, max_body, t0, budget_ms)
        return Response(status, out)
    finally:
        s.close()


def _late(t0, budget_ms):
    if time.ticks_diff(time.ticks_ms(), t0) > budget_ms:
        raise OSError(110, "the response took too long")


def _plain(s, length, cap, t0, budget_ms):
    if length is not None and length > cap:
        raise MemoryError("response too big (%d bytes)" % length)
    parts, n = [], 0
    while length is None or n < length:
        _late(t0, budget_ms)
        b = s.read(min(1024, length - n) if length is not None else 1024)
        if not b:
            break
        n += len(b)
        if n > cap:
            raise MemoryError("response too big")
        parts.append(b)
    return b"".join(parts)


def _plain_into(s, length, buf, t0, budget_ms):
    cap = len(buf)
    if length is not None and length > cap:
        raise MemoryError("response too big (%d bytes)" % length)
    mv, n = memoryview(buf), 0
    while length is None or n < length:
        _late(t0, budget_ms)
        if n == cap:
            if s.read(1):
                raise MemoryError("response too big")
            break
        k = s.readinto(mv[n:min(cap, length) if length is not None else min(cap, n + 1024)])
        if not k:
            break
        n += k
    return mv[:n]


def _chunked_into(s, buf, t0, budget_ms):
    mv, n = memoryview(buf), 0
    while True:
        _late(t0, budget_ms)
        size = int(s.readline().split(b";")[0].strip(), 16)
        if size == 0:
            break
        if n + size > len(buf):
            raise MemoryError("response too big")
        end = n + size
        while n < end:
            _late(t0, budget_ms)
            k = s.readinto(mv[n:end])
            if not k:
                raise OSError("connection closed mid-chunk")
            n += k
        s.readline()
    return mv[:n]


def _chunked(s, cap, t0, budget_ms):
    parts, n = [], 0
    while True:
        _late(t0, budget_ms)
        size = int(s.readline().split(b";")[0].strip(), 16)
        if size == 0:
            break
        n += size
        if n > cap:
            raise MemoryError("response too big")
        left = size
        while left:
            _late(t0, budget_ms)
            b = s.read(min(1024, left))
            if not b:
                raise OSError("connection closed mid-chunk")
            parts.append(b)
            left -= len(b)
        s.readline()
    return b"".join(parts)
