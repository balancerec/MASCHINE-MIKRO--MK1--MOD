"""Serialized coordinator with explicit clock, endpoint and recovery ownership.

No thread or HID reader. Owner must call advance even when input is silent.
"""
import ctypes as C
from .native import Batch, PumpResult, Send, possible_count

class Coordinator:
    def __init__(self, engine, backend, retry_timeout_us, pump_budget=32):
        if type(retry_timeout_us) is not int or not 0 < retry_timeout_us < 2**31:
            raise ValueError('Positive retry timeout below 2^31 microseconds required')
        if type(pump_budget) is not int or not 1 <= pump_budget <= 64:
            raise ValueError('Pump budget must be 1..64')
        self.engine, self.backend = engine, backend
        self.lib = engine.lib
        self.retry_timeout_us, self.pump_budget = retry_timeout_us, pump_budget
        self.phase, self.reason = 'stopped', None
        self.last_now = self.last_native_now = None
        self.retry_since = None
        self.input_generation = self.output_generation = None
        self.endpoint = None
        self.last_error = None
        self._sender = Send(self._send)

    def _send(self, context, message):
        try:
            status = int(self.backend.send(list(message[:3])))
            if status == 3:
                self.last_error = getattr(self.backend, 'last_error', None)
            return status
        except Exception as error:
            self.last_error = str(error)
            return 3

    def _clock(self, now):
        if type(now) is not int or now < 0 or (self.last_now is not None and now < self.last_now):
            raise ValueError('Expected nondecreasing integer microseconds')
        self.last_now = now

    def _clean(self):
        output = self.engine.output
        return not (output.count or output.recovering or output.blocked or possible_count(output))

    def start(self, now):
        self._clock(now)
        if self.phase != 'stopped' or not self._clean() or not self.backend.ready:
            raise RuntimeError('Start requires stopped/clean state and an explicitly opened backend')
        if self.endpoint is not None and self.backend.identity != self.endpoint:
            raise RuntimeError('Cannot switch the owned endpoint')
        batch = Batch()
        if not self.lib.mk1_pad_stream_connect(C.byref(self.engine.stream), now & 0xffffffff, C.byref(batch)):
            raise RuntimeError('Native stream connection failed')
        if batch.count or batch.reset_flags:
            raise RuntimeError('Unexpected dirty stream at start')
        self.endpoint = self.backend.identity
        self.input_generation = self.engine.stream.generation
        self.output_generation = self.engine.output.generation
        self.last_native_now = now
        self.phase, self.reason, self.retry_since = 'running', None, None
        return self.input_generation

    def _recover(self, now, reason, output_already_reset=False):
        ignored = Batch()
        if not self.lib.mk1_pad_stream_disconnect(C.byref(self.engine.stream), now & 0xffffffff,
                                                C.byref(ignored)):
            raise RuntimeError('Native stream disconnect failed')
        # Output owns the accepted/uncertain-note ledger. Producer cleanup is
        # discarded here: pending input onsets may never have reached output.
        if not output_already_reset:
            if not self.lib.mk1_midi_output_recover(C.byref(self.engine.output)):
                raise RuntimeError('Native output recovery failed')
        self.last_native_now = now
        self.phase, self.reason, self.retry_since = 'recovering', reason, None

    def _submit(self, batch, now):
        status = self.lib.mk1_midi_output_submit(C.byref(self.engine.output), self.output_generation,
                                               C.byref(batch))
        if status in (4, 5):
            self._recover(now, 'queue full' if status == 4 else 'input reset', True)
        elif status != 1:
            self._recover(now, 'invalid current producer batch')
            self.phase = 'fault'

    def _pump(self, now):
        if self.phase not in ('running', 'recovering'):
            return
        if self.backend.identity != self.endpoint or not self.backend.ready:
            if self.phase == 'running':
                self._recover(now, 'backend unavailable or endpoint changed')
            self.phase = 'fault'
            return
        result = PumpResult()
        status = self.lib.mk1_midi_output_pump(C.byref(self.engine.output), self._sender, None,
                                              self.pump_budget, C.byref(result))
        if status == 3:
            self._recover(now, 'uncertain MIDI delivery', True)
            self.phase = 'fault'
        elif status == 2:
            if self.retry_since is None:
                self.retry_since = now
            if now - self.retry_since >= self.retry_timeout_us:
                self._recover(now, 'MIDI retry timeout')
                self.phase = 'fault'
        elif status == 1:
            self.retry_since = None
            if self.phase == 'recovering' and self._clean():
                self.phase = 'stopped'
        else:
            self._recover(now, 'native output error')
            self.phase = 'fault'

    def feed(self, report, now, generation, sequence):
        if self.phase != 'running' or generation != self.input_generation:
            return False
        if type(sequence) is not int or not 0 <= sequence < 2**32:
            raise ValueError('Expected an assigned uint32 frame sequence')
        data = bytes(report)
        if not data or data[0] != 32:
            self.advance(now)
            return False
        self._clock(now)
        if now - self.last_native_now >= 2**31:
            self._recover(now, 'clock interval exceeds native range')
            self._pump(now)
            return False
        raw, batch = (C.c_uint8*len(data)).from_buffer_copy(data), Batch()
        accepted = self.lib.mk1_pad_stream_frame(C.byref(self.engine.stream), generation, sequence,
                                                 now & 0xffffffff, raw, len(data), C.byref(batch))
        if accepted:
            self.last_native_now = now
            self._submit(batch, now)
            self._pump(now)
        else:
            self.advance(now)  # duplicates must not keep dead ADC input alive
        return bool(accepted)

    def advance(self, now):
        self._clock(now)
        if self.phase == 'running':
            if now - self.last_native_now >= 2**31:
                self._recover(now, 'clock interval exceeds native range')
            else:
                batch = Batch()
                if not self.lib.mk1_pad_stream_poll(C.byref(self.engine.stream), now & 0xffffffff,
                                                   C.byref(batch)):
                    self._recover(now, 'native clock rejected')
                else:
                    self.last_native_now = now
                    if batch.reset_flags:
                        self._submit(batch, now)
        self._pump(now)

    def stop(self, now):
        self._clock(now)
        if self.phase == 'running':
            self._recover(now, 'explicit stop')
        self._pump(now)
        return self.phase == 'stopped' and self._clean()

    def repair(self, now):
        self._clock(now)
        if self.phase != 'fault' or not self.backend.ready or self.backend.identity != self.endpoint:
            raise RuntimeError('Repair requires the same restored endpoint and a latched fault')
        if not self.lib.mk1_midi_output_resume(C.byref(self.engine.output)):
            raise RuntimeError('Native output resume failed')
        self.phase, self.retry_since = 'recovering', None
        self._pump(now)
        return self.phase == 'stopped'

    def status(self):
        return {'phase': self.phase, 'reason': self.reason, 'queued': self.engine.output.count,
                'possible_notes': possible_count(self.engine.output),
                'blocked': bool(self.engine.output.blocked), 'input_generation': self.input_generation,
                'output_generation': self.engine.output.generation, 'last_error': self.last_error}
