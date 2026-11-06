"""Differential checks against a bounded interpreter of FW55 instructions.

Not a full CPU emulator: only the integer timer path 0x6a22..0x6c72 is
interpreted, with branches into its compiler-generated unrolled helpers.
No USB, port writes or external processes are involved.
"""
import hashlib
import json
import random
import re
from pathlib import Path
from led_pwm_model import LedPwm

ROOT = Path(__file__).resolve().parent
ARCH = ROOT/'fw55-analysis/architecture'
IMAGE_HASH = '8b9363b6155fcd230151ed67bc7d9708cfcd6b912800c2ac6f4ace4c4e0ecb5c'


def load_code():
    image = (ROOT/'fw55-analysis/FW55.bit-normalized.bin').read_bytes()
    assert hashlib.sha256(image).hexdigest() == IMAGE_HASH
    code = {}
    for line in (ARCH/'segment1.annotated.asm').read_text().splitlines():
        match = re.match(r'^([0-9a-f]{8})\s+([0-9a-f]+)\s+(\w+)\s+(.*)', line)
        if not match:
            continue
        addr = int(match[1], 16)
        blob = bytes.fromhex(match[2])
        assert image[addr:addr+len(blob)] == blob
        code[addr] = (len(blob), match[3], match[4])
    return code


def interpret(code, model):
    r = {f'r{i}': 0 for i in range(12)}
    r.update(sp=0x10000, r4=64, r5=0x10028, r6=0x10028, r7=0x10028, r8=model.phase)
    memory = {}
    touched = set()

    def put(addr, value, width):
        for index in range(width):
            memory[addr+index] = (value >> (8*index)) & 255

    def get(addr, width):
        return sum(memory.get(addr+i, 0) << (8*i) for i in range(width))

    put(r['sp']+9*4, model.previous_phase, 4)
    put(r['sp']+7*4, model.deadline, 4)
    for i, v in enumerate(model.mask):
        put(r['r6']+i, v, 1)
    for i, v in enumerate(model.levels):
        put(r['sp']+0x30+4*i, v, 4)

    def val(text):
        return r[text] if text in r else int(text, 0)

    def address(text, scale):
        match = re.fullmatch(r'(\w+)\[(\w+|0x[0-9a-f]+)\]', text)
        if not match:
            raise ValueError(text)
        return val(match[1])+scale*val(match[2])

    pc = 0x6a22
    for _ in range(20000):
        if pc == 0x6c72:
            return {'phase': r['r8'], 'previous_phase': get(r['sp']+36, 4),
                    'deadline': get(r['sp']+28, 4),
                    'mask': bytes(get(r['r6']+i, 1) for i in range(8)),
                    'visited': touched}
        touched.add(pc)
        length, op, tail = code[pc]
        args = [v.strip() for v in tail.split(';')[0].split(',')]
        next_pc = pc+length
        if op in ('bt', 'bf', 'bu'):
            jump = op == 'bu' or (bool(val(args[0])) == (op == 'bt'))
            if jump:
                next_pc = int(re.search(r'file 0x([0-9a-f]+)', tail)[1], 16)
        elif op == 'in':
            r[args[0]] = 0  # timer sample is consumed but not used in this path
        elif op == 'ecallf':
            assert val(args[0]), f'ecallf at {pc:x}'
        elif op in ('ldw', 'ld8u', 'ldaw'):
            width = 1 if op == 'ld8u' else 4
            addr = address(args[1], 1 if op == 'ld8u' else 4)
            r[args[0]] = addr if op == 'ldaw' else get(addr, width)
        elif op in ('stw', 'st8'):
            width = 1 if op == 'st8' else 4
            put(address(args[1], width), val(args[0]), width)
        elif op == 'zext':
            r[args[0]] &= (1 << val(args[1]))-1
        elif op in ('ldc', 'mkmsk', 'not'):
            value = val(args[1])
            r[args[0]] = (value if op == 'ldc' else
                          (1 << value)-1 if op == 'mkmsk' else ~value) & 0xffffffff
        elif op in ('add', 'sub', 'mul', 'shl', 'and', 'lsu', 'eq'):
            a, b = val(args[1]), val(args[2])
            result = {'add': lambda: a+b, 'sub': lambda: a-b,
                      'mul': lambda: a*b, 'shl': lambda: a << b,
                      'and': lambda: a & b, 'lsu': lambda: int(a < b),
                      'eq': lambda: int(a == b)}[op]()
            r[args[0]] = result & 0xffffffff
        else:
            raise NotImplementedError((hex(pc), op, tail))
        pc = next_pc
    raise RuntimeError('Instruction budget exhausted')


def main():
    code = load_code()
    rng = random.Random(55)
    scenarios = [[0]*64, [31]*64, [i % 32 for i in range(64)]]
    scenarios += [[v if i == slot else 0 for i in range(64)]
                  for slot in range(64) for v in (1, 15, 30, 31)]
    scenarios += [[rng.randrange(32) for _ in range(64)] for _ in range(80)]
    visited = set()
    steps = 0
    for levels in scenarios:
        model = LedPwm(levels)
        # Includes timer rollover and in-cycle level changes.
        model.deadline = 0xffff0000
        for iteration in range(40):
            if iteration == 10:
                model.set_level(rng.randrange(64), 65535)
            if iteration == 20:
                model.set_level(rng.randrange(64), 0)
            expected = interpret(code, model)
            model.tick()
            assert expected['mask'] == model.mask
            assert expected['phase'] == model.phase
            assert expected['previous_phase'] == model.previous_phase
            assert expected['deadline'] == model.deadline
            visited.update(expected['visited'])
            steps += 1
    bulk = LedPwm([0]*64)
    bulk.load_bulk([255]*64)
    assert bulk.levels == [31]*64
    demo = LedPwm([0, 1, 8, 16, 31]+[0]*59)
    example = [demo.tick() for _ in range(6)]
    result = {'firmware_sha256': IMAGE_HASH, 'hardware_access': False,
              'method': 'bounded interpretation of byte-checked disassembly versus readable translation',
              'scenarios': len(scenarios), 'differential_steps': steps,
              'unique_instruction_addresses': len(visited), 'demo': example,
              'limits': ['Interpreter implements a subset, not the full XS1 CPU.',
                         'No validation of electrical timing or LED current polarity.',
                         'Physical slot mapping is separate from internal bit packing.']}
    (ARCH/'led-pwm-validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('scenarios', 'differential_steps', 'unique_instruction_addresses')}))


if __name__ == '__main__':
    main()
