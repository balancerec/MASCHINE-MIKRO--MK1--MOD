"""ctypes declarations for the native host test ABI; not a wire format."""
import ctypes as C

class Config(C.Structure):
    _fields_ = [('peak_ticks', C.c_uint32), ('release_ticks', C.c_uint32),
                ('retrigger_ticks', C.c_uint32), ('attack', C.c_uint16),
                ('release', C.c_uint16), ('full_scale', C.c_uint16),
                ('control', C.c_uint8), ('midi_channel', C.c_uint8), ('note', C.c_uint8)]

class Detector(C.Structure):
    _fields_ = [('config', Config), ('last_tick', C.c_uint32), ('attack_tick', C.c_uint32),
                ('below_tick', C.c_uint32), ('off_tick', C.c_uint32), ('peak', C.c_uint16),
                ('phase', C.c_uint8), ('armed', C.c_uint8), ('below', C.c_uint8),
                ('has_tick', C.c_uint8), ('has_off', C.c_uint8)]

class Event(C.Structure):
    _fields_ = [('tick', C.c_uint32), ('kind', C.c_int), ('delta', C.c_int16),
                ('control', C.c_uint8), ('channel', C.c_uint8), ('number', C.c_uint8), ('value', C.c_uint8)]

class Events(C.Structure):
    _fields_ = [('events', Event*2), ('count', C.c_uint8)]

def load(path):
    lib = C.CDLL(str(path.resolve()))
    lib.mk1_pad_detector_init.argtypes = [C.POINTER(Detector), C.POINTER(Config)]
    lib.mk1_pad_detector_sample.argtypes = [C.POINTER(Detector), C.c_uint16, C.c_uint32, C.POINTER(Events)]
    lib.mk1_pad_detector_flush.argtypes = [C.POINTER(Detector), C.c_uint32, C.POINTER(Events)]
    for name in ('mk1_pad_detector_init', 'mk1_pad_detector_sample', 'mk1_pad_detector_flush'):
        getattr(lib, name).restype = C.c_int
    return lib

def read_events(batch):
    return [{'tick': event.tick, 'kind': event.kind, 'value': event.value,
             'control': event.control, 'channel': event.channel, 'note': event.number}
            for event in list(batch.events)[:batch.count]]
