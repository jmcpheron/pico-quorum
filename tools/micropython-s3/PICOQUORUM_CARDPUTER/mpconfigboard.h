// The name ends up in os.uname().machine, "PicoQuorum Cardputer with ESP32S3": board.py picks its
// "cardputer" profile from the ESP32S3 in it.
#define MICROPY_HW_BOARD_NAME               "PicoQuorum Cardputer"
#define MICROPY_HW_MCU_NAME                 "ESP32S3"

// The REPL on USB only: GPIO43/44 are the IR LED's side of the Stamp-S3A, not a UART.
#define MICROPY_HW_ENABLE_UART_REPL         (0)

// ROMFS: the console image in the "romfs" partition, mounted at /rom and run in place from flash.
#define MICROPY_VFS_ROM                     (1)

// No Bluetooth: the firmware uses none, and NimBLE's RAM goes to the heap.
#define MICROPY_PY_BLUETOOTH                (0)

// The REPL on the S3's own USB-Serial-JTAG port, as the stock M5 firmware has it, not TinyUSB.
// TinyUSB's port jumps to the bootloader on a DTR/RTS pattern that macOS's serial driver makes as
// mpremote closes and reopens it: the board fell off USB between tools/fw's sessions (2026-10-12).
// The hardware port resets only on esptool's own sequence.
#define MICROPY_HW_ENABLE_USBDEV            (0)
