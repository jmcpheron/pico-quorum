"""Recovery must reach USB without importing display/network, even with the key released later."""
from pathlib import Path
import sys
import types
from unittest.mock import patch

boot = Path(__file__).resolve().parents[1] / 'firmware' / 'boot.py'
for marker, held in ((True, False), (False, True)):
    board = types.SimpleNamespace(MAINT=1, LED="LED")
    class Pin:
        IN, OUT, PULL_UP = 0, 1, 2
        def __init__(self, *args): pass
        def value(self): return 0 if held else 1
        def on(self): pass
    with patch.dict(sys.modules, {'board': board, 'machine': types.SimpleNamespace(Pin=Pin),
                                  'lcd': None, 'net': None, 'splash': None}), \
         patch('os.listdir', return_value=['maint'] if marker else []):
        exec(compile(boot.read_text(), str(boot), 'exec'), {})
        assert board.MAINTENANCE
print('maintenance: file and physical key both skip display/network imports')
