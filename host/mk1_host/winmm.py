"""Explicit WinMM note-only backend. Import/enumeration never opens a port."""
import ctypes as C
from dataclasses import dataclass
import sys

@dataclass(frozen=True)
class PortKey:
    name: str
    manufacturer: int
    product: int
    version: int
    technology: int

@dataclass(frozen=True)
class Port:
    index: int
    key: PortKey

class Caps(C.Structure):
    _fields_ = [('manufacturer', C.c_uint16), ('product', C.c_uint16), ('version', C.c_uint32),
                ('name', C.c_wchar*32), ('technology', C.c_uint16), ('voices', C.c_uint16),
                ('notes', C.c_uint16), ('channel_mask', C.c_uint16), ('support', C.c_uint32)]

class WinMMApi:
    def __init__(self):
        if sys.platform != 'win32':
            raise OSError('WinMM is available only on Windows')
        self.dll = C.WinDLL('winmm')
        for name in ('midiOutGetNumDevs', 'midiOutGetDevCapsW', 'midiOutOpen', 'midiOutClose', 'midiOutShortMsg'):
            getattr(self.dll, name).restype = C.c_uint
        self.dll.midiOutGetDevCapsW.argtypes = [C.c_size_t, C.POINTER(Caps), C.c_uint]
        self.dll.midiOutOpen.argtypes = [C.POINTER(C.c_void_p), C.c_uint, C.c_size_t, C.c_size_t, C.c_uint32]
        self.dll.midiOutClose.argtypes = [C.c_void_p]
        self.dll.midiOutShortMsg.argtypes = [C.c_void_p, C.c_uint32]

    def key(self, device):
        caps = Caps()
        code = self.dll.midiOutGetDevCapsW(device, C.byref(caps), C.sizeof(caps))
        if code:
            raise OSError(f'midiOutGetDevCapsW failed: {code}')
        return PortKey(caps.name, caps.manufacturer, caps.product, caps.version, caps.technology)

    def ports(self):
        return [Port(index, self.key(index)) for index in range(self.dll.midiOutGetNumDevs())]

    def open(self, index):
        handle = C.c_void_p()
        code = self.dll.midiOutOpen(C.byref(handle), index, 0, 0, 0)
        if code:
            raise OSError(f'midiOutOpen failed: {code}')
        return handle.value

    def opened_key(self, handle):
        return self.key(handle)

    def short(self, handle, packed):
        return self.dll.midiOutShortMsg(handle, packed)

    def close(self, handle):
        return self.dll.midiOutClose(handle)

class WinMMBackend:
    def __init__(self, api=None):
        self.api = api if api is not None else WinMMApi()
        self.handle = None
        self.identity = None
        self.faulted = False
        self.last_error = None
        self.messages_attempted = 0
        self.messages_accepted = 0

    @property
    def ready(self):
        return self.handle is not None and not self.faulted

    def open(self, name):
        if not isinstance(name, str) or not name.strip() or self.handle is not None:
            raise ValueError('Choose an exact port name and close the previous handle first')
        if name.casefold() in ('maschine mikro out', 'microsoft gs wavetable synth', 'microsoft midi mapper'):
            raise ValueError('This path requires a dedicated virtual MIDI destination')
        candidates = [port for port in self.api.ports() if port.key.name == name]
        if len(candidates) != 1 or candidates[0].key.technology != 1:
            raise ValueError('Expected exactly one named MIDI-port destination; no fallback used')
        selected = candidates[0]
        if self.identity is not None and selected.key != self.identity:
            raise RuntimeError('Endpoint identity changed; cleanup cannot switch destinations')
        self.handle = self.api.open(selected.index)
        try:
            if self.api.opened_key(self.handle) != selected.key:
                raise RuntimeError('Port changed between enumeration and opening')
        except Exception:
            self.close()
            raise
        self.identity = selected.key
        self.faulted = False

    def send(self, message):
        data = list(message)
        if (len(data) != 3 or any(type(v) is not int or not 0 <= v <= 255 for v in data) or
            data[0] & 0xf0 not in (0x80, 0x90) or data[1] > 127 or data[2] > 127 or
            (data[0] & 0xf0 == 0x90 and data[2] == 0) or (data[0] & 0xf0 == 0x80 and data[2] != 0)):
            raise ValueError('Expected a complete note-on/off message')
        if self.faulted:
            return 3
        if self.handle is None:
            return 2  # no OS call, therefore definitely not sent
        self.messages_attempted += 1
        try:
            code = self.api.short(self.handle, data[0] | data[1] << 8 | data[2] << 16)
        except Exception as error:
            self.last_error = str(error)
            self.faulted = True
            return 3
        if code:
            self.last_error = f'midiOutShortMsg failed: {code}'
            self.faulted = True
            return 3  # conservative: no proof of absence of delivery
        self.messages_accepted += 1
        return 1

    def close(self):
        if self.handle is None:
            return
        code = self.api.close(self.handle)
        if code:
            self.faulted = True
            self.last_error = f'midiOutClose failed: {code}'
            raise OSError(self.last_error)
        self.handle = None
        self.faulted = False
