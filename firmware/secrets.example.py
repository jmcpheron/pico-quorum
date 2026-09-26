# Copy to secrets.py (gitignored) and fill in.
WIFI_SSID = "your-ssid"
WIFI_PASS = "your-password"
HOSTNAME = "picowallet"
APP_URL = "http://<mac-lan-ip>:3001"
DEVICE_NAME = "picowallet"
# The PicoQuorum console (quorum.py). On the laptop: tools/quorum's Family Safe, simulated or on
# the Anvil fork (`tools/quorum ip` or `tools/quorum up` prints this line).
QUORUM_URL = "http://<mac-lan-ip>:8787"
# A real Safe (docs/LADDER.md): Safe's transaction service, the Safe itself, and an API key from
# developer.safe.global. The key's quota is monthly, so poll gently: every QUORUM_POLL_S seconds,
# and every QUORUM_IDLE_POLL_S after 10 minutes with no key press and no change in the queue.
# QUORUM_URL = "https://api.safe.global/tx-service/basesep"      # or .../tx-service/base
# QUORUM_API_KEY = "..."
# QUORUM_SAFE = {"chainId": 84532, "address": "0x...", "name": "Test Safe"}
# QUORUM_POLL_S = 20
# QUORUM_IDLE_POLL_S = 120
QUORUM_THEME = "dark"   # or "light"
# The console pins which chip, slot and key it signs with (tools/fw pin writes this line). The
# production image signs nothing without it, or when the chip in the board doesn't match.
# QUORUM_EXPECT = {"serial": "0123...", "slot": 0, "owner": "0x...", "locked": True}
# HTTPS certificates are checked against the roots in firmware/ca_*.bin. A development board may
# turn that off; the production image ignores this.
# QUORUM_TLS_VERIFY = True

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
