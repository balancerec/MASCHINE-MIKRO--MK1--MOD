#include "mk1_core.h"

static int config_valid(const mk1_pad_config *config) {
    return config && config->release < config->attack &&
           config->attack < config->full_scale && config->full_scale <= 4095 &&
           config->peak_ticks > 0 && config->peak_ticks < UINT32_C(0x80000000) &&
           config->release_ticks > 0 && config->release_ticks < UINT32_C(0x80000000) &&
           config->retrigger_ticks < UINT32_C(0x80000000) &&
           config->midi_channel >= 1 && config->midi_channel <= 16 && config->note <= 127;
}

static void make_event(mk1_control_event *event, const mk1_pad_config *config,
                        uint32_t tick, mk1_event_kind kind, uint8_t value) {
    event->tick = tick; event->kind = kind; event->delta = 0;
    event->control = config->control; event->channel = config->midi_channel;
    event->number = config->note; event->value = value;
}

static uint8_t velocity(const mk1_pad_config *config, uint16_t peak) {
    uint32_t numerator;
    if (peak >= config->full_scale) return 127;
    numerator = (uint32_t)(peak - config->attack) * UINT32_C(126);
    return (uint8_t)(1u + numerator / (uint32_t)(config->full_scale - config->attack));
}

int mk1_pad_detector_init(mk1_pad_detector *state, const mk1_pad_config *config) {
    mk1_pad_detector fresh = {0};
    if (!state || !config_valid(config)) return 0;
    fresh.config = *config;
    fresh.phase = MK1_PAD_IDLE;
    *state = fresh;
    return 1;
}

int mk1_pad_detector_sample(mk1_pad_detector *state, uint16_t adc,
                            uint32_t tick, mk1_pad_events *events) {
    uint32_t elapsed;
    int release_ready;
    if (!state || !events || !config_valid(&state->config) || adc > 4095 ||
        state->phase > MK1_PAD_HELD || state->armed > 1 || state->below > 1 ||
        state->has_tick > 1 || state->has_off > 1 ||
        (state->phase != MK1_PAD_IDLE &&
         (state->peak < state->config.attack || state->peak > 4095))) return 0;
    if (state->has_tick && (uint32_t)(tick - state->last_tick) >= UINT32_C(0x80000000)) return 0;
    events->count = 0;
    state->last_tick = tick; state->has_tick = 1;

    if (state->phase == MK1_PAD_IDLE) {
        /* Retire elapsed cooldowns so an old off_tick cannot become a fresh
         * cooldown again after a complete timer wrap during a long idle. */
        if (state->has_off && (uint32_t)(tick - state->off_tick) >= state->config.retrigger_ticks)
            state->has_off = 0;
        if (adc <= state->config.release) state->armed = 1;
        if (adc >= state->config.attack && state->armed) {
            state->armed = 0;
            if (state->has_off && (uint32_t)(tick - state->off_tick) < state->config.retrigger_ticks)
                return 1; /* Consume the crossing; do not create a delayed hit. */
            state->phase = MK1_PAD_PEAK;
            state->peak = adc; state->attack_tick = tick; state->below = 0;
        }
        return 1;
    }

    if (adc <= state->config.release) {
        if (!state->below) { state->below = 1; state->below_tick = tick; }
    } else state->below = 0;
    release_ready = state->below &&
        (uint32_t)(tick - state->below_tick) >= state->config.release_ticks;

    if (state->phase == MK1_PAD_PEAK) {
        elapsed = (uint32_t)(tick - state->attack_tick);
        if (elapsed <= state->config.peak_ticks && adc > state->peak) state->peak = adc;
        if (elapsed < state->config.peak_ticks) return 1;
        make_event(&events->events[events->count++], &state->config, tick,
                   MK1_EVENT_NOTE_ON, velocity(&state->config, state->peak));
        state->phase = MK1_PAD_HELD;
    }
    if (release_ready) {
        make_event(&events->events[events->count++], &state->config, tick, MK1_EVENT_NOTE_OFF, 0);
        state->phase = MK1_PAD_IDLE; state->off_tick = tick;
        state->has_off = 1; state->below = 0; state->armed = 0;
    }
    return 1;
}

int mk1_pad_detector_flush(mk1_pad_detector *state, uint32_t tick, mk1_pad_events *events) {
    mk1_pad_detector fresh = {0};
    if (!state || !events || !config_valid(&state->config) || state->phase > MK1_PAD_HELD) return 0;
    events->count = 0;
    if (state->phase == MK1_PAD_HELD) {
        make_event(&events->events[0], &state->config, tick, MK1_EVENT_NOTE_OFF, 0);
        events->count = 1;
    }
    fresh.config = state->config;
    fresh.phase = MK1_PAD_IDLE;
    *state = fresh;
    return 1;
}
