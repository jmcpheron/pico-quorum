# Copy to secrets.py (gitignored) and fill in.
# WiFi is optional here: without it the board opens the WiFi setup screen at power-up (wifisetup.py)
# and keeps what is set there in wifi.json, which it tries first.
WIFI_SSID = "your-ssid"
WIFI_PASS = "your-password"
HOSTNAME = "picoquorum"
DEVICE_NAME = "picoquorum"
# The PicoQuorum console (quorum.py). On the laptop: tools/quorum's Family Safe, simulated or on
# the Anvil fork (`tools/quorum ip` or `tools/quorum up` prints this line).
QUORUM_URL = "http://<mac-lan-ip>:8787"
# Real Safes (docs/guide/SETUP.md): the Safes this console signs for, up to 4, on any of the chains
# in firmware/quorum_cfg.py "services" (1 Ethereum, 8453 Base, 84532 Base Sepolia). Each is asked
# about at its own chain's service, so leave QUORUM_URL out. Plus an API key from
# developer.safe.global. The key's quota is monthly, so poll gently: one Safe every QUORUM_POLL_S
# seconds, in turn, and every QUORUM_IDLE_POLL_S after 10 minutes with no key press and no change.
# QUORUM_SAFES = [
#     {"chainId": 8453, "address": "0x...", "name": "Family Safe"},
#     {"chainId": 1, "address": "0x...", "name": "Vault"},
# ]
# QUORUM_API_KEY = "..."
# QUORUM_POLL_S = 20
# QUORUM_IDLE_POLL_S = 120
# The screensaver: after this many quiet seconds on home with nothing to sign, the backlight dims
# and the screen turns over the time, each Safe, this key, the last approval and the release. Any
# key wakes it; a transaction for this key wakes it to the queue. 0 turns it off.
# QUORUM_SAVER_S = 60
# The clock card's time zone, in hours from UTC (it says UTC when this is 0).
# QUORUM_UTC_OFFSET = -7
QUORUM_THEME = "dark"   # or "light"
# The boot screen: "pixel" (the default: the PicoQuorum mark turning into Ethereum in pixel art, 8 steps a
# second, ~3.8 s), "mark" (the same in smooth vectors, ~3.7 s), "still" (the finished mark at once), "orbit"
# (the full orbit animation, ~8-10 fps) or "checklist".
# BOOT_ART = "pixel"
# Its taglines (firmware/taglines.py): "serious" (the default), "fun", "all" or "none".
# BOOT_TAGLINES = "serious"
# The console pins which chip, slot and key it signs with (tools/fw pin writes this line). With a
# pin, it signs nothing when the chip in the board doesn't match. Without one, it signs with any chip.
# QUORUM_EXPECT = {"serial": "0123...", "slot": 0, "owner": "0x...", "locked": True}
# HTTPS certificates are checked against the roots in firmware/ca_*.bin. A development board may
# turn that off; the production image ignores this.
# QUORUM_TLS_VERIFY = True

# Passwordless MicroPython REPL on TCP/2323. Full signer control: isolated development only.
ENABLE_NETWORK_CONSOLE = False

# Without an ATECC608 the wallet stops on a NO CHIP screen. True runs it on a throwaway software
# key instead (the emulator does this); never on a board that should hold value.
ALLOW_SOFT_KEY = False
# Provisioning a FRESH chip, from the app's Setup page or the wallet's own KEYS screen (X on the
# home screen). All of it is permanent; leave both False on a wallet that holds value.
ALLOW_LOCK = False     # lock the config zone (required before the chip will make a key), the data zone, or one slot
ALLOW_GENKEY = False   # make a new key in a slot, replacing the one there
# The hardware (firmware/board.py). "waveshare" (the default): the Pico-LCD-1.3, 240x240 with the
# joystick and A/B/X/Y. "build1": the 2.0" screen as 320x240 and the knob (hardware/wiring/BUILD1.md).
# An ESP32 is always "esp32" (hardware/wiring/ESP32.md), whatever this says; SCREEN still applies.
# BOARD = "build1"
# SCREEN = "2.8"       # build1 and esp32: "2.8", "2.4" or "2.0" (240x320), or "1.8" (128x160)
# ATECC608 bus pins. GP4/GP5 is the wallet wiring (GPIO21/22 on an ESP32); set these only for a
# board where those pins are taken (a clone with something on GP5, say). Any two free GPIOs work.
# ATECC_SDA = 4
# ATECC_SCL = 5
