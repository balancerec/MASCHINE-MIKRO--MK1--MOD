"""Explicit dry-run destination. Never forwards to any MIDI API."""
class MemoryBackend:
    ready = True
    identity = ('memory-only',)
    def __init__(self):
        self.messages = []
        self.active = set()
    def send(self, message):
        data = list(message)
        route = (data[0] & 15, data[1])
        if data[0] & 0xf0 == 0x90:
            if route in self.active:
                raise RuntimeError('Overlapping onset in dry-run receiver')
            self.active.add(route)
        else:
            self.active.discard(route)
        self.messages.append(data)
        return 1
