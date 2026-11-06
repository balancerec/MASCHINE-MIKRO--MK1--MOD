#include "mk1_core.h"

int mk1_encoder_init(mk1_encoder *state) {
    if (!state) return 0;
    state->previous = 3; state->gate = 0; state->position = 0;
    state->ambiguous_returns = 0;
    return 1;
}

int mk1_encoder_sample(mk1_encoder *state, uint8_t serial_byte, int8_t *delta) {
    uint8_t current;
    int8_t change = 0;
    if (!state || !delta || state->previous > 3 || state->gate > 3) return 0;
    current = (uint8_t)((serial_byte >> 1) & 3u);
    if (current == state->gate) {
        if (current != 0) state->gate = 0;
        else {
            if (state->previous == 1) {
                state->position = (uint8_t)(state->position + 1u); change = 1;
            } else if (state->previous == 2) {
                state->position = (uint8_t)(state->position - 1u); change = -1;
            } else state->ambiguous_returns += UINT32_C(1);
            state->gate = 3;
        }
    }
    state->previous = current;
    *delta = change;
    return 1;
}

int mk1_hid_encoder_init(mk1_hid_encoder *state) {
    if (!state) return 0;
    state->valid = 0; state->position = 0; state->pressed = 0;
    return 1;
}

int mk1_hid_encoder_read(mk1_hid_encoder *state, const uint8_t *report,
                          size_t length, mk1_hid_encoder_event *event) {
    int delta;
    uint8_t position, pressed;
    if (!state || !report || !event || length < 6 || report[0] != 1 ||
        state->valid > 1 || state->position > 15 || state->pressed > 1) return 0;
    position = (uint8_t)(report[5] & 15u);
    pressed = (uint8_t)((report[2] & 8u) != 0);
    delta = state->valid ? ((int)position - (int)state->position + 24) % 16 - 8 : 0;
    event->ambiguous = (uint8_t)(delta == -8);
    event->delta = (int8_t)(delta == -8 ? 0 : delta);
    event->baseline = (uint8_t)!state->valid;
    event->position = position; event->pressed = pressed;
    event->push_changed = state->valid ? (uint8_t)(pressed != state->pressed) : pressed;
    state->valid = 1; state->position = position; state->pressed = pressed;
    return 1;
}

int mk1_led_init(mk1_led_pwm *state, const uint8_t *levels, size_t count,
                  uint32_t deadline) {
    size_t i;
    if (!state || !levels || count != MK1_LED_SLOTS) return 0;
    for (i = 0; i < MK1_LED_SLOTS; ++i) if (levels[i] > 31) return 0;
    for (i = 0; i < MK1_LED_SLOTS; ++i) state->levels[i] = levels[i];
    for (i = 0; i < MK1_LED_BYTES; ++i) state->mask[i] = 255;
    state->phase = 0; state->previous_phase = 0; state->deadline = deadline;
    return 1;
}

int mk1_led_set(mk1_led_pwm *state, size_t slot, uint16_t value) {
    if (!state || slot >= MK1_LED_SLOTS) return 0;
    state->levels[slot] = (uint8_t)(value > 31 ? 31 : value);
    return 1;
}

int mk1_led_load(mk1_led_pwm *state, const uint8_t *values, size_t count) {
    size_t i;
    if (!state || !values || count != MK1_LED_SLOTS) return 0;
    for (i = 0; i < MK1_LED_SLOTS; ++i) state->levels[i] = (uint8_t)(values[i] & 31u);
    return 1;
}

int mk1_led_tick(mk1_led_pwm *state, mk1_led_update *update) {
    size_t slot;
    uint8_t cutoff, next = 31;
    uint32_t delta;
    if (!state || !update || state->phase > 31 || state->previous_phase > 31) return 0;
    for (slot = 0; slot < MK1_LED_SLOTS; ++slot) if (state->levels[slot] > 31) return 0;
    update->phase_at_entry = state->phase;
    if (state->phase == 31) {
        for (slot = 0; slot < MK1_LED_BYTES; ++slot) state->mask[slot] = 255;
        state->previous_phase = 0; cutoff = 0;
    } else cutoff = state->phase;
    for (slot = 0; slot < MK1_LED_SLOTS; ++slot) {
        if (state->levels[slot] <= cutoff)
            state->mask[slot / 8] &= (uint8_t)~(1u << (slot % 8));
    }
    for (slot = 0; slot < MK1_LED_SLOTS; ++slot) {
        if ((state->mask[slot / 8] & (1u << (slot % 8))) && state->levels[slot] < next)
            next = state->levels[slot];
    }
    delta = (uint32_t)next - (uint32_t)state->previous_phase;
    state->deadline += delta * MK1_LED_TICKS_PER_LEVEL;
    state->previous_phase = next; state->phase = next;
    update->next_phase = next; update->deadline = state->deadline;
    for (slot = 0; slot < MK1_LED_BYTES; ++slot) {
        update->frame.bytes[slot] = state->mask[slot];
        update->wire_frame.bytes[slot] = state->mask[MK1_LED_BYTES - 1 - slot];
    }
    return 1;
}

int mk1_pad_report_read(const uint8_t *report, size_t length, uint32_t tick,
                         mk1_pad_sample samples[MK1_PAD_SAMPLES]) {
    size_t i;
    uint8_t counts[2][MK1_PAD_CHANNELS] = {{0}};
    if (!report || !samples || length < 65 || report[0] != 32) return 0;
    /* Each scan contains each tagged channel once. Validate before output. */
    for (i = 0; i < MK1_PAD_SAMPLES; ++i) {
        uint8_t channel = (uint8_t)(report[2 + 2*i] >> 4);
        if (++counts[i / MK1_PAD_CHANNELS][channel] != 1) return 0;
    }
    for (i = 0; i < MK1_PAD_SAMPLES; ++i) {
        uint16_t word = (uint16_t)((uint16_t)report[1 + 2*i] |
                                   ((uint16_t)report[2 + 2*i] << 8));
        samples[i].tick = tick;
        samples[i].adc = (uint16_t)(word & 4095u);
        samples[i].channel = (uint8_t)(word >> 12);
        samples[i].scan = (uint8_t)(i / MK1_PAD_CHANNELS);
    }
    return 1;
}
