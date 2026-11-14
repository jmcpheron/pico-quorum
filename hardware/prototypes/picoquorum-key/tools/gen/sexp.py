"""Minimal S-expression reader/writer for KiCad files.

Lists are Python lists; quoted strings are QStr; bare atoms are plain str.
"""


class QStr(str):
    """A string that is written back with quotes."""


def parse(text):
    pos, n = 0, len(text)
    stack, cur = [], []
    while pos < n:
        c = text[pos]
        if c in " \t\r\n":
            pos += 1
        elif c == "(":
            stack.append(cur)
            cur = []
            pos += 1
        elif c == ")":
            done = cur
            cur = stack.pop()
            cur.append(done)
            pos += 1
        elif c == '"':
            pos += 1
            buf = []
            while text[pos] != '"':
                if text[pos] == "\\":
                    pos += 1
                    buf.append({"n": "\n", "t": "\t", "\\": "\\", '"': '"'}.get(text[pos], "\\" + text[pos]))
                else:
                    buf.append(text[pos])
                pos += 1
            pos += 1
            cur.append(QStr("".join(buf)))
        else:
            start = pos
            while pos < n and text[pos] not in ' \t\r\n()"':
                pos += 1
            cur.append(text[start:pos])
    assert not stack, "unbalanced"
    return cur[0] if len(cur) == 1 else cur


def _atom(x):
    if isinstance(x, QStr):
        return '"' + x.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, float):
        s = ("%.4f" % x).rstrip("0").rstrip(".")
        return "0" if s in ("-0", "") else s
    return str(x)


def dumps(node, indent=0):
    """Write with one list per line once a list holds other lists, like KiCad does."""
    if not isinstance(node, list):
        return _atom(node)
    if not any(isinstance(x, list) for x in node):
        return "(" + " ".join(_atom(x) for x in node) + ")"
    pad = "\t" * (indent + 1)
    head = []
    rest = []
    for x in node:
        (rest if (rest or isinstance(x, list)) else head).append(x)
    out = "(" + " ".join(_atom(x) for x in head)
    for x in rest:
        out += "\n" + pad + dumps(x, indent + 1)
    return out + "\n" + "\t" * indent + ")"


def find(node, key):
    """First child list whose head is key."""
    for x in node:
        if isinstance(x, list) and x and x[0] == key:
            return x
    return None


def find_all(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]
