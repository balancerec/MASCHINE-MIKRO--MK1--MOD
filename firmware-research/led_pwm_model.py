"""Readable translation of the FW55 LED timer path. No hardware access.

Internal slots 0..63 are not physical pad numbers or HID report offsets.
Timing is expressed in firmware timer ticks, not wall-clock seconds.
"""
from dataclasses import dataclass, field

TICKS_PER_LEVEL = 0x493E


@dataclass
class LedPwm:
    levels: list[int]
    mask: bytearray = field(default_factory=lambda: bytearray([255]*8))
    phase: int = 0
    previous_phase: int = 0
    deadline: int = 0

    def __post_init__(self):
        if len(self.levels) != 64 or any(type(v) is not int or not 0 <= v <= 31
                                         for v in self.levels):
            raise ValueError('Expected 64 internal brightness values in 0..31')
        self.levels = list(self.levels)

    def set_level(self, slot, value):
        """Single-slot command path clamps the low 16-bit value to 31."""
        if type(slot) is not int or not 0 <= slot < 64:
            raise ValueError('Invalid internal LED slot')
        if type(value) is not int or not 0 <= value <= 65535:
            raise ValueError('Command value must be an unsigned 16-bit integer')
        self.levels[slot] = min(value, 31)

    def load_bulk(self, values):
        """Bulk path masks bytes to five bits instead of saturating them."""
        if len(values) != 64 or any(type(v) is not int or not 0 <= v <= 255 for v in values):
            raise ValueError('Expected 64 unsigned bytes')
        self.levels[:] = [value & 31 for value in values]

    def tick(self):
        phase_at_entry = self.phase
        if self.phase == 31:
            self.mask[:] = b'\xff'*8
            self.previous_phase = 0
            cutoff = 0
        else:
            cutoff = self.phase

        # Only clear bits. New brightness values do not relight an already
        # cleared slot until the next phase-31 reset of the mask.
        for slot, level in enumerate(self.levels):
            if level <= cutoff:
                self.mask[slot // 8] &= ~(1 << (slot % 8)) & 255

        next_phase = min((self.levels[slot] for slot in range(64)
                          if self.mask[slot // 8] & (1 << (slot % 8))), default=31)
        self.phase = next_phase
        delta = (next_phase - self.previous_phase) & 0xffffffff
        self.previous_phase = next_phase
        self.deadline = (self.deadline + delta*TICKS_PER_LEVEL) & 0xffffffff
        return {'phase_at_entry': phase_at_entry, 'next_phase': next_phase,
                'deadline': self.deadline, 'mask_hex': self.mask.hex(),
                'wire_byte_order_hex': bytes(reversed(self.mask)).hex()}
