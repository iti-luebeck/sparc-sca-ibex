#!/usr/bin/env python3
"""Generate masked AES-128 test vectors as C headers."""

from __future__ import annotations

import argparse
import os
import random
from pathlib import Path

AES_KEY_SIZE = 16
AES_BLOCK_SIZE = 16
DEFAULT_FIXED_KEY = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")


def _rand_bytes(n: int, rng: random.Random) -> bytes:
    return bytes(rng.randrange(0, 256) for _ in range(n))


def _fmt_bytes(data: bytes) -> str:
    return ", ".join(f"0x{b:02x}" for b in data)


def _write_header(path: Path, vector_id: int, key: bytes, key_mask: bytes,
                  key_share0: bytes, plaintext: bytes, state_mask: bytes) -> None:
    guard = f"VECTOR_{vector_id:04d}_H"
    content = f"""#ifndef {guard}
#define {guard}

#include <stdint.h>

#define VECTOR_ID {vector_id}

__attribute__((section(\".tainted_data\")))
const uint8_t aes_key_share0[{AES_KEY_SIZE}] = {{ { _fmt_bytes(key_share0) } }};

const uint8_t aes_key_mask[{AES_KEY_SIZE}] = {{ { _fmt_bytes(key_mask) } }};
const uint8_t aes_state_mask[{AES_BLOCK_SIZE}] = {{ { _fmt_bytes(state_mask) } }};
const uint8_t aes_plaintext[{AES_BLOCK_SIZE}] = {{ { _fmt_bytes(plaintext) } }};

#endif /* {guard} */
"""
    path.write_text(content)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate masked AES-128 test vectors.")
    parser.add_argument("--out-dir", default="test_patterns", help="Output directory")
    parser.add_argument("--count", type=int, default=1, help="Number of vectors to generate")
    parser.add_argument("--seed", type=int, default=None, help="PRNG seed")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--fixed-key", help="Fixed key as 32 hex chars")
    group.add_argument("--random-key", action="store_true", help="Random key per vector")

    args = parser.parse_args()

    if args.count <= 0:
        raise SystemExit("--count must be > 0")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)

    if args.fixed_key:
        fixed_key = bytes.fromhex(args.fixed_key)
        if len(fixed_key) != AES_KEY_SIZE:
            raise SystemExit("--fixed-key must be 16 bytes (32 hex chars)")
    else:
        fixed_key = DEFAULT_FIXED_KEY

    manifest_lines = []

    for i in range(args.count):
        key = _rand_bytes(AES_KEY_SIZE, rng) if args.random_key else fixed_key
        key_mask = _rand_bytes(AES_KEY_SIZE, rng)
        key_share0 = bytes(k ^ m for k, m in zip(key, key_mask))
        plaintext = _rand_bytes(AES_BLOCK_SIZE, rng)
        state_mask = _rand_bytes(AES_BLOCK_SIZE, rng)

        header_name = f"vector_{i:04d}.h"
        header_path = out_dir / header_name
        _write_header(header_path, i, key, key_mask, key_share0, plaintext, state_mask)
        manifest_lines.append(header_name)

    (out_dir / "manifest.txt").write_text("\n".join(manifest_lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
