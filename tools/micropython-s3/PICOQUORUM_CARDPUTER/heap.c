// More Python heap, from the IDF heap's regions that Wi-Fi and TLS leave alone (mpconfigboard.h).
// On the Cardputer these are a 32 KB and a 22 KB region beside the 289 KB main one. Wi-Fi took 30 KB
// of the main one and none of these, and a TLS handshake failed with OSError 12 while the 32 KB one
// was free (2026-10-12). Each region's largest free block is taken once, at the first boot, and
// added to the Python heap after every gc_init (soft resets too).
#include "py/gc.h"
#include "esp_heap_caps.h"
#define MULTI_HEAP_FREERTOS
#include "../multi_heap_platform.h"     // IDF's private heap list, as modesp32.c's idf_heap_info reads it
#include "../heap_private.h"

#define EXTRA_MIN (16 * 1024)           // a smaller block is not worth an area (the RTC's 8 KB)
#define EXTRA_MAX 3

static void *extra[EXTRA_MAX];
static size_t extra_size[EXTRA_MAX];
static size_t n_extra;
static bool taken;

void picoquorum_gc_init(void *main_heap) {
    if (!taken) {
        taken = true;
        heap_t *heap;
        SLIST_FOREACH(heap, &registered_heaps, next) {
            if (n_extra == EXTRA_MAX) {
                break;
            }
            if ((intptr_t)main_heap >= heap->start && (intptr_t)main_heap < heap->end) {
                continue;               // the main region: Wi-Fi's, TLS's and the system's
            }
            if (!heap_caps_match(heap, MALLOC_CAP_8BIT)) {
                continue;               // instruction RAM
            }
            multi_heap_info_t info;
            multi_heap_get_info(heap->heap, &info);
            if (info.largest_free_block < EXTRA_MIN) {
                continue;
            }
            void *p = multi_heap_malloc(heap->heap, info.largest_free_block);
            if (p != NULL) {
                extra[n_extra] = p;
                extra_size[n_extra++] = info.largest_free_block;
            }
        }
    }
    for (size_t i = 0; i < n_extra; i++) {
        gc_add(extra[i], (char *)extra[i] + extra_size[i]);
    }
}
