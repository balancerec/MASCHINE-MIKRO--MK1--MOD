#include "mk1_core.h"

static int stream_valid(const mk1_pad_stream *state) {
    return state && state->max_gap_ticks > 0 &&
           state->max_gap_ticks < UINT32_C(0x80000000) &&
           state->connected <= 1 && state->has_frame <= 1;
}

static int append_events(mk1_stream_events *events, const mk1_pad_events *batch) {
    size_t i;
    if ((size_t)events->count + batch->count > MK1_STREAM_MAX_EVENTS) return 0;
    for (i = 0; i < batch->count; ++i) events->events[events->count++] = batch->events[i];
    return 1;
}

static int flush_all(mk1_pad_stream *state, uint32_t tick, mk1_stream_events *events) {
    size_t channel;
    for (channel = 0; channel < MK1_PAD_CHANNELS; ++channel) {
        mk1_pad_events batch;
        if (!mk1_pad_detector_flush(&state->pads[channel], tick, &batch) ||
            !append_events(events, &batch)) return 0;
    }
    return 1;
}

int mk1_pad_stream_init(mk1_pad_stream *state, const mk1_pad_config *configs,
                         size_t count, uint32_t max_gap_ticks) {
    mk1_pad_stream fresh = {0};
    size_t channel, previous;
    if (!state || !configs || count != MK1_PAD_CHANNELS || max_gap_ticks == 0 ||
        max_gap_ticks >= UINT32_C(0x80000000)) return 0;
    for (channel = 0; channel < count; ++channel) {
        for (previous = 0; previous < channel; ++previous) {
            if (configs[channel].control == configs[previous].control ||
                (configs[channel].midi_channel == configs[previous].midi_channel &&
                 configs[channel].note == configs[previous].note)) return 0;
        }
        if (!mk1_pad_detector_init(&fresh.pads[channel], &configs[channel])) return 0;
    }
    fresh.max_gap_ticks = max_gap_ticks;
    *state = fresh;
    return 1;
}

int mk1_pad_stream_connect(mk1_pad_stream *state, uint32_t tick, mk1_stream_events *events) {
    mk1_pad_stream next;
    mk1_stream_events pending = {0};
    if (!events || !stream_valid(state)) return 0;
    next = *state;
    if (!flush_all(&next, tick, &pending)) return 0;
    if (next.connected) pending.reset_flags = MK1_STREAM_RECONNECT;
    next.generation += UINT32_C(1);
    next.connected = 1; next.has_frame = 0;
    next.clock_tick = tick; next.last_frame_tick = tick;
    *state = next; *events = pending;
    return 1;
}

int mk1_pad_stream_disconnect(mk1_pad_stream *state, uint32_t tick, mk1_stream_events *events) {
    mk1_pad_stream next;
    mk1_stream_events pending = {0};
    if (!events || !stream_valid(state)) return 0;
    next = *state;
    if (!flush_all(&next, tick, &pending)) return 0;
    if (next.connected) pending.reset_flags = MK1_STREAM_DISCONNECT;
    next.connected = 0; next.has_frame = 0; next.clock_tick = tick;
    *state = next; *events = pending;
    return 1;
}

int mk1_pad_stream_frame(mk1_pad_stream *state, uint32_t generation,
                          uint32_t sequence, uint32_t tick,
                          const uint8_t *report, size_t length, mk1_stream_events *events) {
    mk1_pad_stream next;
    mk1_stream_events pending = {0};
    mk1_pad_sample samples[MK1_PAD_SAMPLES];
    uint16_t values[MK1_PAD_CHANNELS] = {0};
    uint32_t sequence_delta = 1;
    size_t i;
    if (!events || !stream_valid(state) || !report || length == 0 || report[0] != 32 ||
        !state->connected || generation != state->generation ||
        (uint32_t)(tick - state->clock_tick) >= UINT32_C(0x80000000)) return 0;
    if (state->has_frame) {
        sequence_delta = (uint32_t)(sequence - state->last_sequence);
        if (sequence_delta == 0 || sequence_delta >= UINT32_C(0x80000000)) return 0;
    }
    next = *state;
    next.clock_tick = tick;
    if (!mk1_pad_report_read(report, length, tick, samples)) {
        if (!flush_all(&next, tick, &pending)) return 0;
        next.connected = 0; next.has_frame = 0;
        pending.reset_flags = MK1_STREAM_MALFORMED;
        *state = next; *events = pending;
        return 1;
    }
    if (state->has_frame && sequence_delta > 1) pending.reset_flags |= MK1_STREAM_SEQUENCE_GAP;
    if ((uint32_t)(tick - state->last_frame_tick) > state->max_gap_ticks)
        pending.reset_flags |= MK1_STREAM_TIME_GAP;
    if (pending.reset_flags && !flush_all(&next, tick, &pending)) return 0;
    for (i = 0; i < MK1_PAD_SAMPLES; ++i) {
        if (samples[i].adc > values[samples[i].channel]) values[samples[i].channel] = samples[i].adc;
    }
    for (i = 0; i < MK1_PAD_CHANNELS; ++i) {
        mk1_pad_events batch;
        if (!mk1_pad_detector_sample(&next.pads[i], values[i], tick, &batch) ||
            !append_events(&pending, &batch)) return 0;
    }
    next.last_frame_tick = tick; next.last_sequence = sequence; next.has_frame = 1;
    *state = next; *events = pending;
    return 1;
}

int mk1_pad_stream_poll(mk1_pad_stream *state, uint32_t tick, mk1_stream_events *events) {
    mk1_pad_stream next;
    mk1_stream_events pending = {0};
    if (!events || !stream_valid(state)) return 0;
    if (!state->connected) { *events = pending; return 1; }
    if ((uint32_t)(tick - state->clock_tick) >= UINT32_C(0x80000000)) return 0;
    next = *state;
    next.clock_tick = tick;
    if ((uint32_t)(tick - state->last_frame_tick) > state->max_gap_ticks) {
        if (!flush_all(&next, tick, &pending)) return 0;
        next.connected = 0; next.has_frame = 0;
        pending.reset_flags = MK1_STREAM_WATCHDOG;
    }
    *state = next; *events = pending;
    return 1;
}
