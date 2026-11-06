#ifndef MK1_CORE_H
#define MK1_CORE_H

#include <stddef.h>
#include <stdint.h>

#if defined(_WIN32) && defined(MK1_CORE_SHARED)
#define MK1_API __declspec(dllexport)
#else
#define MK1_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

enum { MK1_LED_SLOTS = 64, MK1_LED_BYTES = 8, MK1_PAD_CHANNELS = 16,
       MK1_PAD_SAMPLES = 32, MK1_LCD_WIDTH = 128, MK1_LCD_PAGES = 8 };
#define MK1_LED_TICKS_PER_LEVEL UINT32_C(18750)

/* Application contracts, NOT packed USB structures or a stable binary ABI.
 * Ticks have an adapter-defined timebase. Channels are 0..15; physical pad
 * numbers require the separately calibrated map. */
typedef struct {
    uint32_t tick;
    uint16_t adc;                 /* 0..4095 */
    uint8_t channel;
    uint8_t scan;                 /* 0 or 1 within an input report */
} mk1_pad_sample;

typedef enum {
    MK1_EVENT_NOTE_ON, MK1_EVENT_NOTE_OFF, MK1_EVENT_PRESSURE,
    MK1_EVENT_BUTTON, MK1_EVENT_ENCODER
} mk1_event_kind;

/* Reserved contract for a future musical processor. No MIDI emission exists
 * here. MIDI channel is 1..16; data fields 0..127, encoder delta signed. */
typedef struct {
    uint32_t tick;
    mk1_event_kind kind;
    int16_t delta;
    uint8_t control, channel, number, value;
} mk1_control_event;

typedef struct { uint8_t bytes[MK1_LED_BYTES]; } mk1_led_frame;

/* Page-major monochrome bytes; adapter consumes/copies borrowed data before
 * caller releases it. One byte represents eight vertical pixels.
 * No display driver or ownership transfer is implemented by this contract. */
typedef struct {
    uint16_t x, page, width, page_count;
    const uint8_t *data;
    size_t length;
} mk1_display_update;

typedef struct {
    uint8_t previous, gate, position;
    uint32_t ambiguous_returns;
} mk1_encoder;

/* Defaults reproduce the model inputs, not a proof of every boot initializer. */
MK1_API int mk1_encoder_init(mk1_encoder *state);
/* Second serial button byte; bits 1/2 are quadrature. delta is -1,0,+1.
 * Invalid pointers/state return 0 without mutation. */
MK1_API int mk1_encoder_sample(mk1_encoder *state, uint8_t serial_byte, int8_t *delta);

typedef struct { uint8_t valid, position, pressed; } mk1_hid_encoder;
typedef struct {
    int8_t delta;
    uint8_t position, pressed, push_changed, baseline, ambiguous;
} mk1_hid_encoder_event;
MK1_API int mk1_hid_encoder_init(mk1_hid_encoder *state);
/* Report01, first six bytes including ID. Eight-step jumps are ambiguous:
 * delta=0, ambiguous=1, reference updated. Larger unseen motion cannot be
 * recovered. Caller owns accumulation and resets on disconnect/gaps. */
MK1_API int mk1_hid_encoder_read(mk1_hid_encoder *state, const uint8_t *report,
                                 size_t length, mk1_hid_encoder_event *event);

typedef struct {
    uint8_t levels[MK1_LED_SLOTS];
    uint8_t mask[MK1_LED_BYTES];
    uint8_t phase, previous_phase;
    uint32_t deadline;
} mk1_led_pwm;
typedef struct {
    mk1_led_frame frame;          /* memory order */
    mk1_led_frame wire_frame;     /* byte7 first; not HID report80 */
    uint8_t phase_at_entry, next_phase;
    uint32_t deadline;
} mk1_led_update;
MK1_API int mk1_led_init(mk1_led_pwm *state, const uint8_t *levels, size_t count,
                         uint32_t deadline);
MK1_API int mk1_led_set(mk1_led_pwm *state, size_t slot, uint16_t value);
MK1_API int mk1_led_load(mk1_led_pwm *state, const uint8_t *values, size_t count);
MK1_API int mk1_led_tick(mk1_led_pwm *state, mk1_led_update *update);

/* Parse report20 little-endian words by their channel tags. No attack,
 * velocity, pressure mapping or musical threshold is applied. Invalid
 * reports leave the output untouched. Output must not overlap input. */
MK1_API int mk1_pad_report_read(const uint8_t *report, size_t length, uint32_t tick,
                               mk1_pad_sample samples[MK1_PAD_SAMPLES]);

#ifdef __cplusplus
}
#endif
#endif
