"""Exhaustive single-step differential checks of the encoder decoder.

Uses the byte-checked instruction listing, interpreting only 0x6250..0x62a8.
This does not emulate the hardware input circuit or the full processor.
"""
import json
import random
import re
from pathlib import Path
from encoder_model import Encoder
from verify_led_pwm import load_code, IMAGE_HASH

ARCH = Path(__file__).resolve().parent/'fw55-analysis/architecture'


def interpret(code, byte, model):
    registers = {'r0': byte, 'r1': 0, 'r2': 0, 'r3': 0}
    dp = {4: model.previous, 5: model.gate, 0x2d: model.ambiguous_returns,
          0x2e: model.position}
    visited = set()

    def value(text):
        return registers[text] if text in registers else int(text, 0)

    pc = 0x6250
    for _ in range(80):
        visited.add(pc)
        length, op, text = code[pc]
        args = [a.strip() for a in text.split(';')[0].split(',')]
        next_pc = pc + length
        if op == 'retsp':
            return (dp[4], dp[5], dp[0x2e], dp[0x2d]), visited
        if op in ('bu', 'bf', 'bt'):
            if op == 'bu' or bool(value(args[0])) == (op == 'bt'):
                next_pc = int(re.search(r'file 0x([0-9a-f]+)', text)[1], 16)
        elif op in ('ldw', 'stw'):
            slot = int(re.fullmatch(r'dp\[(.*?)\]', args[1])[1], 0)
            if op == 'ldw':
                registers[args[0]] = dp[slot]
            else:
                dp[slot] = value(args[0])
        elif op == 'zext':
            registers[args[0]] &= (1 << value(args[1]))-1
        elif op in ('mkmsk', 'ldc'):
            v = value(args[1])
            registers[args[0]] = (1 << v)-1 if op == 'mkmsk' else v
        elif op in ('ashr', 'and', 'eq', 'add', 'sub'):
            a, b = value(args[1]), value(args[2])
            if op == 'ashr':
                a = a if a < 0x80000000 else a-0x100000000
                out = a >> b
            elif op == 'and':
                out = a & b
            elif op == 'eq':
                out = int(a == b)
            elif op == 'add':
                out = a+b
            else:
                out = a-b
            registers[args[0]] = out & 0xffffffff
        else:
            raise NotImplementedError((pc, op))
        pc = next_pc
    raise RuntimeError('Decoder instruction budget exceeded')


def state(model):
    return model.previous, model.gate, model.position, model.ambiguous_returns


def main():
    code = load_code()
    count = 0
    visited = set()
    # All input bytes, possible quadrature/gate states, and counter boundaries.
    for previous in range(4):
        for gate in range(4):
            for position in (0, 1, 127, 254, 255):
                for byte in range(256):
                    for errors in (0, 0xffffffff):
                        model = Encoder(previous, gate, position, errors)
                        expected, addresses = interpret(code, byte, model)
                        model.sample(byte)
                        assert state(model) == expected
                        visited.update(addresses)
                        count += 1
    rng = random.Random(55)
    model = Encoder()
    for _ in range(10000):
        byte = rng.randrange(256)
        expected, _ = interpret(code, byte, model)
        model.sample(byte)
        assert state(model) == expected
    examples = {}
    for name, samples in {'positive': [3, 1, 0], 'negative': [3, 2, 0],
                          'bounce': [3, 1, 0, 1, 0], 'ambiguous': [3, 0]}.items():
        model = Encoder()
        deltas = [model.sample(s << 1) for s in samples]
        examples[name] = {'quadrature_states': samples, 'deltas': deltas,
                          'final': state(model)}
    assert examples['positive']['deltas'] == [0, 0, 1]
    assert examples['negative']['deltas'] == [0, 0, -1]
    assert examples['bounce']['final'][2] == 1
    assert examples['ambiguous']['final'][3] == 1
    result = {'firmware_sha256': IMAGE_HASH, 'hardware_access': False,
              'single_step_cases': count, 'random_sequence_samples': 10000,
              'instruction_addresses_covered': len(visited), 'examples': examples,
              'limits': ['Logical sign is not a measured clockwise/counterclockwise direction.',
                         'No physical bounce or sample-rate validation.',
                         'Counter 0x2d is named by observed behavior; original symbol unknown.',
                         'Constructor counter defaults are model inputs, not a proven full boot initialization.']}
    (ARCH/'encoder-validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if isinstance(v, int)}))


if __name__ == '__main__':
    main()
