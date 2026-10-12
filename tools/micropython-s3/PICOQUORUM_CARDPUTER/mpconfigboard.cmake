# MicroPython for the Cardputer console: ESP32_GENERIC_S3 without Bluetooth (the firmware uses none),
# PSRAM (the Stamp-S3A has none) or TinyUSB (the REPL is on the S3's USB-Serial-JTAG), and with
# ROMFS, so the console runs from flash (README.md).
set(IDF_TARGET esp32s3)

set(SDKCONFIG_DEFAULTS
    boards/sdkconfig.base
    boards/PICOQUORUM_CARDPUTER/sdkconfig.board
)
