# Copy to secrets.py (gitignored) and fill in.
WIFI_SSID = "your-ssid"
WIFI_PASS = "your-password"
HOSTNAME = "picowallet"
APP_URL = "http://<mac-lan-ip>:3001"
DEVICE_NAME = "picowallet"
# The PicoQuorum console (quorum.py): Safe's transaction service, or tools/quorum's simulated Safe
# on the laptop (`tools/quorum ip` prints this line). QUORUM_API_KEY for api.safe.global, if set.
QUORUM_URL = "http://<mac-lan-ip>:8787"
QUORUM_THEME = "dark"   # or "light"

# Passwordless MicroPython REPL on TCP/2323. Full signer control: isolated development only.
ENABLE_NETWORK_CONSOLE = False

# Production forks: pin all three after deploying. None keeps the PoC development workflow flexible.
EXPECTED_CHAIN_ID = None
EXPECTED_VAULT = None
EXPECTED_TOKEN = None
# Without an ATECC608 the wallet stops on a NO CHIP screen. True runs it on a throwaway software
# key instead (the emulator does this); never on a board that should hold value.
ALLOW_SOFT_KEY = False
# Provisioning a FRESH chip, from the app's Setup page or the wallet's own KEYS screen (X on the
# home screen). All of it is permanent; leave both False on a wallet that holds value.
ALLOW_LOCK = False     # lock the config zone (required before the chip will make a key), the data zone, or one slot
ALLOW_GENKEY = False   # make a new key in a slot, replacing the one there
# ATECC608 bus pins. GP4/GP5 is the wallet wiring; set these only for a board where those pins
# are taken (a clone with something on GP5, say). Any two free GPIOs work.
# ATECC_SDA = 4
# ATECC_SCL = 5
