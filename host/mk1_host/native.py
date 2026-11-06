"""Production host ctypes binding; validate ABI before using native state."""
import ctypes as C
from pathlib import Path

class Config(C.Structure):
    _fields_ = [('peak_ticks', C.c_uint32), ('release_ticks', C.c_uint32), ('retrigger_ticks', C.c_uint32),
                ('attack', C.c_uint16), ('release', C.c_uint16), ('full_scale', C.c_uint16),
                ('control', C.c_uint8), ('midi_channel', C.c_uint8), ('note', C.c_uint8)]

class Detector(C.Structure):
    _fields_ = [('config', Config), ('last_tick', C.c_uint32), ('attack_tick', C.c_uint32),
                ('below_tick', C.c_uint32), ('off_tick', C.c_uint32), ('peak', C.c_uint16),
                ('phase', C.c_uint8), ('armed', C.c_uint8), ('below', C.c_uint8),
                ('has_tick', C.c_uint8), ('has_off', C.c_uint8)]

class Event(C.Structure):
    _fields_ = [('tick', C.c_uint32), ('kind', C.c_int), ('delta', C.c_int16),
                ('control', C.c_uint8), ('channel', C.c_uint8), ('number', C.c_uint8), ('value', C.c_uint8)]

class Batch(C.Structure):
    _fields_ = [('events', Event*32), ('count', C.c_uint8), ('reset_flags', C.c_uint8)]

class Stream(C.Structure):
    _fields_ = [('pads', Detector*16), ('generation', C.c_uint32), ('clock_tick', C.c_uint32),
                ('last_frame_tick', C.c_uint32), ('last_sequence', C.c_uint32),
                ('max_gap_ticks', C.c_uint32), ('connected', C.c_uint8), ('has_frame', C.c_uint8)]

class Message(C.Structure):
    _fields_ = [('bytes', C.c_uint8*3)]

class Output(C.Structure):
    _fields_ = [('queue', Message*64), ('possible_notes', (C.c_uint8*16)*16),
                ('generation', C.c_uint32), ('head', C.c_uint8), ('count', C.c_uint8),
                ('recovering', C.c_uint8), ('blocked', C.c_uint8)]

class PumpResult(C.Structure):
    _fields_ = [('attempted', C.c_uint8), ('accepted', C.c_uint8)]

Send = C.CFUNCTYPE(C.c_int, C.c_void_p, C.POINTER(C.c_uint8))

def possible_count(output):
    return sum(int(byte).bit_count() for row in output.possible_notes for byte in row)

class NativeEngine:
    def __init__(self, library, configs, max_gap_us):
        if not isinstance(max_gap_us, int) or not 0 < max_gap_us < 2**31 or len(configs) != 16:
            raise ValueError('Expected 16 channel configs and a positive gap below 2^31 microseconds')
        self.lib = C.CDLL(str(Path(library).resolve()))
        lib = self.lib
        lib.mk1_core_abi_version.argtypes = []
        lib.mk1_core_abi_version.restype = C.c_uint32
        lib.mk1_core_layout_size.argtypes = [C.c_uint]
        lib.mk1_core_layout_size.restype = C.c_size_t
        if lib.mk1_core_abi_version() != 1:
            raise RuntimeError('Native ABI version mismatch; rebuild the host core')
        for index, struct in enumerate((Config, Stream, Batch, Output, PumpResult), 1):
            if lib.mk1_core_layout_size(index) != C.sizeof(struct):
                raise RuntimeError('Native ABI layout mismatch; rebuild matching sources')
        signatures = {
            'mk1_pad_stream_init': [C.POINTER(Stream), C.POINTER(Config), C.c_size_t, C.c_uint32],
            'mk1_pad_stream_connect': [C.POINTER(Stream), C.c_uint32, C.POINTER(Batch)],
            'mk1_pad_stream_disconnect': [C.POINTER(Stream), C.c_uint32, C.POINTER(Batch)],
            'mk1_pad_stream_poll': [C.POINTER(Stream), C.c_uint32, C.POINTER(Batch)],
            'mk1_pad_stream_frame': [C.POINTER(Stream), C.c_uint32, C.c_uint32, C.c_uint32,
                                      C.POINTER(C.c_uint8), C.c_size_t, C.POINTER(Batch)],
            'mk1_midi_output_init': [C.POINTER(Output)],
            'mk1_midi_output_submit': [C.POINTER(Output), C.c_uint32, C.POINTER(Batch)],
            'mk1_midi_output_recover': [C.POINTER(Output)],
            'mk1_midi_output_resume': [C.POINTER(Output)],
            'mk1_midi_output_pump': [C.POINTER(Output), Send, C.c_void_p, C.c_size_t, C.POINTER(PumpResult)],
        }
        for name, arguments in signatures.items():
            getattr(lib, name).argtypes = arguments
            getattr(lib, name).restype = C.c_int
        self.stream, self.output = Stream(), Output()
        values = (Config*16)(*configs)
        if not lib.mk1_pad_stream_init(C.byref(self.stream), values, 16, max_gap_us):
            raise ValueError('Invalid native pad configuration or overlapping routes')
        if not lib.mk1_midi_output_init(C.byref(self.output)):
            raise RuntimeError('Native output initialization failed')
