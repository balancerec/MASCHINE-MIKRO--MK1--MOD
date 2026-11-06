"""Offline translation of FW55 function 0x6250 (encoder state machine).

The two quadrature bits are bits 1 and 2 of the second serial input byte.
Positive/negative changes are logical; clockwise direction is not established.
"""
from dataclasses import dataclass


def hid_position_delta(previous, current):
    """Normal HID exposes only four position bits; slow-motion delta.

    Eight or more steps between reports cannot be resolved unambiguously.
    Rightward motion was observed as +1 in the physical capture.
    """
    if any(type(v) is not int or not 0 <= v < 16 for v in (previous, current)):
        raise ValueError('Expected four-bit HID positions')
    return ((current - previous + 8) % 16) - 8


@dataclass
class Encoder:
    previous: int = 3
    gate: int = 0
    position: int = 0
    ambiguous_returns: int = 0

    def sample(self, serial_byte):
        if type(serial_byte) is not int or not 0 <= serial_byte <= 255:
            raise ValueError('Expected an unsigned serial input byte')
        state = (serial_byte >> 1) & 3
        before = self.position
        if state == self.gate:
            if state:
                self.gate = 0
            else:
                if self.previous == 1:
                    self.position = (self.position + 1) & 255
                elif self.previous == 2:
                    self.position = (self.position - 1) & 255
                else:
                    self.ambiguous_returns = (self.ambiguous_returns + 1) & 0xffffffff
                self.gate = 3
        self.previous = state
        difference = (self.position - before) & 255
        return 1 if difference == 1 else -1 if difference == 255 else 0
