# AES-128 Masked Key Vector Scenario - Ibex Core

This scenario extends the masked AES implementation with **generated test vectors**.
Each vector is stored in a separate C header under `test_patterns/`, and every
vector is compiled into its own enumerated ELF binary.

## Files

| File | Description |
|------|-------------|
| `main.S` | Minimal entry point (calls `c_main`) |
| `main.c` | Calls `aes128_masked_encrypt` using a selected vector header |
| `aes128_masked.c` | Masked AES implementation |
| `scripts/generate_test_vectors.py` | Generates header files with vectors |
| `test_patterns/` | Vector headers + manifest |

## Generating Vectors

```bash
make generate_vectors COUNT=5              # 5 vectors, fixed key (default)
make generate_vectors COUNT=5 RANDOM_KEY=1 # 5 vectors, random key per vector
make generate_vectors COUNT=5 SEED=1234    # deterministic randomness
make generate_vectors COUNT=3 FIXED_KEY=2b7e151628aed2a6abf7158809cf4f3c
```

Vector headers will be written to `test_patterns/` and listed in `manifest.txt`.

## Building Enumerated Binaries

```bash
make
```

Outputs are created as:

- `build/app_0000.elf`
- `build/app_0001.elf`
- ...

Each binary corresponds to a different vector header.

## Taint Configuration

The masked key share (`aes_key_share0`) is placed in `.tainted_data` at `0xC00`.
Use the taint file:

- `taint_data/scenario_aes128_masked_key_vectors/taint_data.txt`
