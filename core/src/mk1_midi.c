#include "mk1_core.h"

static int valid_output(const mk1_midi_output *state) {
    size_t i;
    if (!state || state->head >= MK1_MIDI_CAPACITY || state->count > MK1_MIDI_CAPACITY ||
        state->recovering > 1 || state->blocked > 1 || (state->recovering && state->count)) return 0;
    for (i = 0; i < state->count; ++i) {
        const mk1_midi_message *message = &state->queue[(state->head + i) % MK1_MIDI_CAPACITY];
        uint8_t kind = (uint8_t)(message->bytes[0] & 0xf0u);
        if ((kind != 0x80u && kind != 0x90u) || message->bytes[1] > 127 || message->bytes[2] > 127 ||
            (kind == 0x80u && message->bytes[2] != 0) ||
            (kind == 0x90u && message->bytes[2] == 0)) return 0;
    }
    return 1;
}

static int note_set(uint8_t notes[16][16], uint8_t channel, uint8_t note, int on) {
    uint8_t bit = (uint8_t)(1u << (note % 8));
    int before = (notes[channel][note / 8] & bit) != 0;
    if (on) notes[channel][note / 8] |= bit;
    else notes[channel][note / 8] &= (uint8_t)~bit;
    return before;
}

static int first_note(const mk1_midi_output *state, mk1_midi_message *message) {
    size_t channel, note;
    for (channel = 0; channel < 16; ++channel) {
        for (note = 0; note < 128; ++note) {
            if (state->possible_notes[channel][note / 8] & (1u << (note % 8))) {
                message->bytes[0] = (uint8_t)(0x80u | channel);
                message->bytes[1] = (uint8_t)note; message->bytes[2] = 0;
                return 1;
            }
        }
    }
    return 0;
}

static void recover_output(mk1_midi_output *state) {
    mk1_midi_message message;
    state->head = 0; state->count = 0; state->blocked = 0;
    state->generation += UINT32_C(1);
    state->recovering = (uint8_t)first_note(state, &message);
}

int mk1_midi_output_init(mk1_midi_output *state) {
    mk1_midi_output fresh = {0};
    if (!state) return MK1_MIDI_INVALID;
    fresh.generation = 1;
    *state = fresh;
    return MK1_MIDI_OK;
}

int mk1_midi_output_recover(mk1_midi_output *state) {
    if (!valid_output(state)) return MK1_MIDI_INVALID;
    recover_output(state);
    return MK1_MIDI_OK;
}

int mk1_midi_output_resume(mk1_midi_output *state) {
    if (!valid_output(state)) return MK1_MIDI_INVALID;
    state->blocked = 0;
    return MK1_MIDI_OK;
}

int mk1_midi_output_submit(mk1_midi_output *state, uint32_t generation,
                           const mk1_stream_events *events) {
    uint8_t planned[16][16];
    mk1_midi_message messages[MK1_STREAM_MAX_EVENTS];
    size_t i, channel, byte;
    if (!valid_output(state) || !events || events->count > MK1_STREAM_MAX_EVENTS ||
        (events->reset_flags & 0xc0u) != 0 || generation != state->generation ||
        state->recovering || state->blocked) return MK1_MIDI_INVALID;
    for (channel = 0; channel < 16; ++channel)
        for (byte = 0; byte < 16; ++byte) planned[channel][byte] = state->possible_notes[channel][byte];
    for (i = 0; i < state->count; ++i) {
        const mk1_midi_message *message = &state->queue[(state->head + i) % MK1_MIDI_CAPACITY];
        (void)note_set(planned, (uint8_t)(message->bytes[0] & 15u), message->bytes[1],
                       (message->bytes[0] & 0xf0u) == 0x90u);
    }
    for (i = 0; i < events->count; ++i) {
        const mk1_control_event *event = &events->events[i];
        int on, was_on;
        if ((event->kind != MK1_EVENT_NOTE_ON && event->kind != MK1_EVENT_NOTE_OFF) ||
            event->channel < 1 || event->channel > 16 || event->number > 127 ||
            event->value > 127) return MK1_MIDI_INVALID;
        on = event->kind == MK1_EVENT_NOTE_ON;
        if ((on && event->value == 0) || (!on && event->value != 0) ||
            (events->reset_flags && on)) return MK1_MIDI_INVALID;
        messages[i].bytes[0] = (uint8_t)((on ? 0x90u : 0x80u) | (event->channel - 1u));
        messages[i].bytes[1] = event->number; messages[i].bytes[2] = event->value;
        if (!events->reset_flags) {
            was_on = note_set(planned, (uint8_t)(event->channel - 1u), event->number, on);
            if (was_on == on) return MK1_MIDI_INVALID; /* overlap or unmatched release */
        }
    }
    if (events->reset_flags) {
        recover_output(state);
        return MK1_MIDI_RESET;
    }
    if ((size_t)state->count + events->count > MK1_MIDI_CAPACITY) {
        recover_output(state);
        return MK1_MIDI_FULL;
    }
    for (i = 0; i < events->count; ++i) {
        state->queue[(state->head + state->count) % MK1_MIDI_CAPACITY] = messages[i];
        ++state->count;
    }
    return MK1_MIDI_OK;
}

int mk1_midi_output_pump(mk1_midi_output *state, mk1_midi_send_fn send,
                         void *context, size_t budget, mk1_midi_pump_result *result) {
    mk1_midi_pump_result pending = {0};
    if (!valid_output(state) || !send || !result || budget == 0 || budget > MK1_MIDI_CAPACITY)
        return MK1_MIDI_INVALID;
    if (state->blocked) { *result = pending; return MK1_MIDI_UNCERTAIN; }
    while (pending.attempted < budget) {
        mk1_midi_message message;
        int status, on;
        uint8_t channel;
        if (state->recovering) {
            if (!first_note(state, &message)) { state->recovering = 0; break; }
        } else {
            if (state->count == 0) break;
            message = state->queue[state->head];
        }
        ++pending.attempted;
        status = send(context, message.bytes);
        on = (message.bytes[0] & 0xf0u) == 0x90u;
        channel = (uint8_t)(message.bytes[0] & 15u);
        if (status == MK1_MIDI_RETRY) { *result = pending; return MK1_MIDI_RETRY; }
        if (status != MK1_MIDI_OK) {
            if (on) (void)note_set(state->possible_notes, channel, message.bytes[1], 1);
            recover_output(state);
            state->blocked = 1;
            *result = pending;
            return MK1_MIDI_UNCERTAIN;
        }
        ++pending.accepted;
        (void)note_set(state->possible_notes, channel, message.bytes[1], on);
        if (!state->recovering) {
            state->head = (uint8_t)((state->head + 1u) % MK1_MIDI_CAPACITY);
            --state->count;
        }
    }
    if (state->recovering) {
        mk1_midi_message message;
        if (!first_note(state, &message)) state->recovering = 0;
    }
    *result = pending;
    return MK1_MIDI_OK;
}
