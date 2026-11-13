#include "mk1_core.h"
#include <stdio.h>

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "Failed line %d: %s\n", __LINE__, #x); return 1; } } while (0)

int main(void) {
    /* Synthetic settings only; these are not measured calibration defaults. */
    mk1_pad_config config = {4, 3, 5, 100, 40, 1000, 1, 1, 36};
    mk1_pad_detector pad;
    mk1_pad_events events;
    CHECK(mk1_pad_detector_init(&pad, &config));
    CHECK(mk1_pad_detector_sample(&pad, 500, 0, &events) && events.count == 0);
    CHECK(mk1_pad_detector_sample(&pad, 0, 1, &events) && events.count == 0);
    CHECK(mk1_pad_detector_sample(&pad, 100, 2, &events) && events.count == 0);
    CHECK(mk1_pad_detector_sample(&pad, 1000, 3, &events) && events.count == 0);
    CHECK(mk1_pad_detector_sample(&pad, 1000, 6, &events) && events.count == 1);
    CHECK(events.events[0].kind == MK1_EVENT_NOTE_ON && events.events[0].value == 127);
    CHECK(mk1_pad_detector_sample(&pad, 2000, 7, &events) && events.count == 0);
    CHECK(mk1_pad_detector_sample(&pad, 0, 8, &events) && events.count == 0);
    CHECK(mk1_pad_detector_sample(&pad, 41, 10, &events) && events.count == 0);
    CHECK(mk1_pad_detector_sample(&pad, 0, 11, &events) && events.count == 0);
    CHECK(mk1_pad_detector_sample(&pad, 0, 14, &events) && events.count == 1);
    CHECK(events.events[0].kind == MK1_EVENT_NOTE_OFF);
    CHECK(mk1_pad_detector_sample(&pad, 0, 15, &events));
    CHECK(mk1_pad_detector_sample(&pad, 900, 16, &events) && events.count == 0);
    CHECK(mk1_pad_detector_sample(&pad, 900, 30, &events) && events.count == 0);
    CHECK(mk1_pad_detector_sample(&pad, 0, 31, &events));
    CHECK(mk1_pad_detector_sample(&pad, 800, 32, &events));
    CHECK(mk1_pad_detector_sample(&pad, 800, 36, &events) && events.count == 1);
    CHECK(mk1_pad_detector_flush(&pad, 37, &events) && events.count == 1);
    CHECK(events.events[0].kind == MK1_EVENT_NOTE_OFF);
    CHECK(mk1_pad_detector_flush(&pad, 37, &events) && events.count == 0);

    CHECK(mk1_pad_detector_sample(&pad, 0, UINT32_MAX - 4, &events));
    CHECK(mk1_pad_detector_sample(&pad, 100, UINT32_MAX - 3, &events));
    CHECK(mk1_pad_detector_sample(&pad, 0, UINT32_MAX - 2, &events));
    CHECK(mk1_pad_detector_sample(&pad, 0, 1, &events) && events.count == 2);
    CHECK(events.events[0].kind == MK1_EVENT_NOTE_ON && events.events[0].value == 1);
    CHECK(events.events[1].kind == MK1_EVENT_NOTE_OFF);
    CHECK(mk1_pad_detector_flush(&pad, 2, &events));
    CHECK(mk1_pad_detector_sample(&pad, 0, 10, &events));
    events.count = 77;
    CHECK(!mk1_pad_detector_sample(&pad, 4096, 11, &events));
    CHECK(events.count == 77 && pad.last_tick == 10);
    CHECK(!mk1_pad_detector_sample(&pad, 0, 9, &events));
    CHECK(events.count == 77 && pad.last_tick == 10);
    config.release = config.attack;
    CHECK(!mk1_pad_detector_init(&pad, &config));
    CHECK(pad.last_tick == 10);
    puts("Pad detector: attack/peak, sustained note, release debounce, cooldown, flush, wrap and invalid input passed.");
    return 0;
}
