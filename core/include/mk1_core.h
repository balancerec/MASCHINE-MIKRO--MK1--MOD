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

/* Detector NOTE_ON/OFF and reserved pressure/button/encoder contract. No MIDI
 * emission exists here. Channel is 1..16; data 0..127, encoder delta signed. */
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

/* Experimental host detector, not a translation of the NI musical processor.
 * All time values use one caller-defined tick domain; durations < 2^31.
 * Configuration is explicit: no measured-device defaults are embedded. */
typedef struct {
    uint32_t peak_ticks, release_ticks, retrigger_ticks;
    uint16_t attack, release, full_scale;
    uint8_t control, midi_channel, note;
} mk1_pad_config;

typedef enum { MK1_PAD_IDLE, MK1_PAD_PEAK, MK1_PAD_HELD } mk1_pad_phase;
typedef struct {
    mk1_pad_config config;
    uint32_t last_tick, attack_tick, below_tick, off_tick;
    uint16_t peak;
    uint8_t phase, armed, below, has_tick, has_off;
} mk1_pad_detector;

/* At most NOTE_ON + NOTE_OFF when a short hit ends inside the peak window. */
typedef struct { mk1_control_event events[2]; uint8_t count; } mk1_pad_events;

MK1_API int mk1_pad_detector_init(mk1_pad_detector *state, const mk1_pad_config *config);
/* Requires a quiet sample <= release to arm after init/flush or a prior hit.
 * Input times must be nondecreasing modulo 2^32 with gaps < 2^31 ticks.
 * Invalid input returns 0 without mutation. Caller routes each channel to
 * its own state; adc is raw 0..4095. No MIDI is sent by this function. */
MK1_API int mk1_pad_detector_sample(mk1_pad_detector *state, uint16_t adc,
                                    uint32_t tick, mk1_pad_events *events);
/* Explicit disconnect/stream-loss cleanup: release an emitted note, discard
 * pending attack, and require quiet baseline again. No clock runs internally. */
MK1_API int mk1_pad_detector_flush(mk1_pad_detector *state, uint32_t tick,
                                   mk1_pad_events *events);

enum {
    MK1_STREAM_MAX_EVENTS = 32,
    MK1_STREAM_SEQUENCE_GAP = 1, MK1_STREAM_TIME_GAP = 2,
    MK1_STREAM_MALFORMED = 4, MK1_STREAM_DISCONNECT = 8,
    MK1_STREAM_WATCHDOG = 16, MK1_STREAM_RECONNECT = 32
};
typedef struct {
    mk1_pad_detector pads[MK1_PAD_CHANNELS]; /* indexed by tagged ADC channel */
    uint32_t generation, clock_tick, last_frame_tick, last_sequence, max_gap_ticks;
    uint8_t connected, has_frame;
} mk1_pad_stream;
typedef struct {
    mk1_control_event events[MK1_STREAM_MAX_EVENTS];
    uint8_t count, reset_flags;
} mk1_stream_events;

/* Config indexed by raw channel. Unique control IDs and (MIDI channel,note)
 * pairs are required; this adapter does not allocate overlapping MIDI voices. */
MK1_API int mk1_pad_stream_init(mk1_pad_stream *state, const mk1_pad_config *configs,
                                size_t count, uint32_t max_gap_ticks);
/* Connect increments generation; attach it to callbacks to reject old sessions.
 * A reconnect flushes active notes. Caller must consume the returned batch. */
MK1_API int mk1_pad_stream_connect(mk1_pad_stream *state, uint32_t tick, mk1_stream_events *events);
MK1_API int mk1_pad_stream_disconnect(mk1_pad_stream *state, uint32_t tick, mk1_stream_events *events);
/* Caller supplies its own report20 sequence and monotonic arrival clock.
 * No hardware sequence counter exists in the parsed report. Both wrap at 2^32.
 * Old/duplicate sequences, stale generations, backward time and unrelated IDs
 * return 0 without mutation. Recoverable gaps return 1 and reset_flags, flush
 * notes and rearm from quiet. A malformed report20 disconnects with note-offs.
 * ADC input is max of the two tagged scans per channel, once per arrival tick. */
MK1_API int mk1_pad_stream_frame(mk1_pad_stream *state, uint32_t generation,
                                 uint32_t sequence, uint32_t tick,
                                 const uint8_t *report, size_t length,
                                 mk1_stream_events *events);
/* Required caller-driven watchdog, including before the first report.
 * A timeout disconnects; a fresh connect/generation is needed to resume. */
MK1_API int mk1_pad_stream_poll(mk1_pad_stream *state, uint32_t tick, mk1_stream_events *events);

#ifdef __cplusplus
}
#endif
#endif
