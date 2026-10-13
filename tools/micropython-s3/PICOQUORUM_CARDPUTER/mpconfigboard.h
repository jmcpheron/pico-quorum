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

// The Python heap never grows. Stock MicroPython starts it at 64 KB and adds to it from the IDF heap
// whenever an allocation fails after a collection, by its own size or the largest block left. The
// console's ~150 KB live and its fragmentation grew it to 239 KB, and the IDF heap had no block
// over 8 KB: every HTTPS request failed with OSError 12, and Wi-Fi stopped starting (2026-10-12).
// Measured with the heap at 208 KB: the system left 35 KB of the main region, Wi-Fi took 30 KB of
// that, and one HTTPS session needs about 31 KB. So 160 KB from the main region, and the rest of
// the Python heap from the regions Wi-Fi and TLS leave alone (heap.c): about 53 KB more.
// patches/split-heap-auto.patch lets the first setting through, patches/board-gc-init.patch adds
// the hook heap.c runs from.
#define MICROPY_GC_SPLIT_HEAP_AUTO          (0)
#define MICROPY_GC_INITIAL_HEAP_SIZE        (160 * 1024)
#define MP_PLAT_ALLOC_HEAP(size)            malloc(size)    // main.c takes the main heap with it;
                                                            // py/mpconfig.h defines it only when the heap can grow
void picoquorum_gc_init(void *main_heap);
#define MICROPY_BOARD_GC_INIT(main_heap)    picoquorum_gc_init(main_heap)

// No mDNS: nothing on the console looks up or answers a .local name, and its task and buffers come
// out of the IDF heap.
#define MICROPY_HW_ENABLE_MDNS_QUERIES      (0)
#define MICROPY_HW_ENABLE_MDNS_RESPONDER    (0)
