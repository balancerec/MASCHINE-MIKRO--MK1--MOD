"""ctypes declarations for the host MIDI queue test ABI; no actual MIDI port."""
import ctypes as C
from test_pad_stream import Batch

class Message(C.Structure):
    _fields_ = [('bytes', C.c_uint8*3)]

class Output(C.Structure):
    _fields_ = [('queue', Message*64), ('possible_notes', (C.c_uint8*16)*16),
                ('generation', C.c_uint32), ('head', C.c_uint8), ('count', C.c_uint8),
                ('recovering', C.c_uint8), ('blocked', C.c_uint8)]

class PumpResult(C.Structure):
    _fields_ = [('attempted', C.c_uint8), ('accepted', C.c_uint8)]

Send = C.CFUNCTYPE(C.c_int, C.c_void_p, C.POINTER(C.c_uint8))

def bind_output(lib):
    for name in ('init', 'recover', 'resume'):
        getattr(lib, 'mk1_midi_output_'+name).argtypes = [C.POINTER(Output)]
    lib.mk1_midi_output_submit.argtypes = [C.POINTER(Output), C.c_uint32, C.POINTER(Batch)]
    lib.mk1_midi_output_pump.argtypes = [C.POINTER(Output), Send, C.c_void_p,
                                        C.c_size_t, C.POINTER(PumpResult)]
    for name in ('init', 'recover', 'resume', 'submit', 'pump'):
        getattr(lib, 'mk1_midi_output_'+name).restype = C.c_int
    return lib

def batch_from_events(events, reset=0):
    batch = Batch()
    batch.count, batch.reset_flags = len(events), reset
    for i, (kind, channel, note, value) in enumerate(events):
        batch.events[i].kind = kind
        batch.events[i].channel = channel
        batch.events[i].number = note
        batch.events[i].value = value
    return batch

def possible(state):
    return {(channel, note) for channel in range(16) for note in range(128)
            if state.possible_notes[channel][note//8] & (1 << (note % 8))}
