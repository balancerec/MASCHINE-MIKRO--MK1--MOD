#include "mk1_core.h"
#include <stdio.h>
#include <string.h>

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "Failed line %d: %s\n", __LINE__, #x); return 1; } } while (0)

int main(void) {
    mk1_encoder encoder;
    int8_t delta;
    mk1_led_pwm pwm, before;
    mk1_led_update update;
    uint8_t levels[64] = {0}, report[65] = {32};
    mk1_pad_sample samples[32];
    size_t i;
    CHECK(mk1_encoder_init(&encoder));
    CHECK(mk1_encoder_sample(&encoder, 6, &delta) && delta == 0);
    CHECK(mk1_encoder_sample(&encoder, 2, &delta) && delta == 0);
    CHECK(mk1_encoder_sample(&encoder, 0, &delta) && delta == 1);
    CHECK(mk1_encoder_sample(&encoder, 2, &delta) && delta == 0);
    CHECK(mk1_encoder_sample(&encoder, 0, &delta) && delta == 0);
    CHECK(!mk1_encoder_sample(&encoder, 0, NULL));
    levels[0] = 31; levels[63] = 1;
    CHECK(mk1_led_init(&pwm, levels, 64, UINT32_MAX - 100));
    CHECK(mk1_led_tick(&pwm, &update));
    CHECK(update.frame.bytes[0] == 1 && update.frame.bytes[7] == 128);
    CHECK(update.wire_frame.bytes[0] == 128 && update.next_phase == 1);
    CHECK(update.deadline == UINT32_C(18649));
    before = pwm;
    CHECK(!mk1_led_set(&pwm, 64, 1));
    CHECK(memcmp(&before, &pwm, sizeof(pwm)) == 0);
    memset(levels, 32, sizeof(levels));
    CHECK(!mk1_led_init(&pwm, levels, 64, 0));
    CHECK(memcmp(&before, &pwm, sizeof(pwm)) == 0);
    CHECK(mk1_led_load(&pwm, levels, 64) && pwm.levels[0] == 0);
    CHECK(mk1_led_set(&pwm, 0, 32) && pwm.levels[0] == 31);
    for (i = 0; i < 32; ++i) {
        uint16_t word = (uint16_t)(((i % 16) << 12) | (i * 127));
        report[1 + 2*i] = (uint8_t)word; report[2 + 2*i] = (uint8_t)(word >> 8);
    }
    CHECK(mk1_pad_report_read(report, sizeof(report), 77, samples));
    CHECK(samples[31].adc == 3937 && samples[31].channel == 15 && samples[31].scan == 1);
    CHECK(samples[0].tick == 77);
    report[4] = 0; /* duplicate channel0 in the first scan */
    samples[0].adc = 999;
    CHECK(!mk1_pad_report_read(report, sizeof(report), 88, samples));
    CHECK(samples[0].adc == 999 && samples[0].tick == 77);
    puts("C contracts: encoder, PWM, overflow, invalid inputs and tagged pad samples passed.");
    return 0;
}
