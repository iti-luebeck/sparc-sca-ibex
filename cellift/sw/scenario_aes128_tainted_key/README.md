# AES-128 Tainted Key Scenario for CellIFT - Ibex Core

This scenario demonstrates information flow tracking through AES-128 encryption
using CellIFT on the Ibex (RV32IMC) processor.

## Purpose

Observe how taint propagates from a secret cryptographic key through the entire
AES encryption algorithm. Ibex is a simpler in-order core compared to CVA6,
making taint flow easier to observe.

## Architecture

- **Core**: Ibex (RV32IMC)
- **Mode**: Machine mode only (no MMU/virtual memory)
- **Memory**: Simple flat memory model starting at 0x80

## Files

| File | Description |
|------|-------------|
| `main.S` | Entry point, data definitions, calls AES |
| `aes128.c` | AES-128 implementation in C |
| `link.ld` | Linker script with tainted section |
| `Makefile` | Build configuration |

## Memory Layout

```
0x00000080  .text.init    (entry point)
0x00000180  .text         (AES code)
0x00000280  .rodata       (S-box table)
0x00000380  .data         (plaintext, ciphertext, context)
0x00000480  .bss
0x00000580  stack
0x00000980  .tainted_data (AES KEY - TAINT THIS!)
```

## Taint Configuration

In CellIFT simulation, mark the following as tainted:

- **Address**: `tainted_region_start` (symbol in linker script)
- **Size**: 16 bytes (AES key)
- **Label**: `aes_key`

## Building

```bash
make clean
make
```

Outputs:
- `build/app.elf` - Executable
- `build/app.elf.dump` - Disassembly

## Test Vectors (FIPS-197 Appendix B)

| Data | Value |
|------|-------|
| Key | `2b7e151628aed2a6abf7158809cf4f3c` |
| Plaintext | `3243f6a8885a308d313198a2e0370734` |
| Ciphertext | `3925841d02dc09fbdc118597196a0b32` |

## Execution Flow

1. `_start`: Set up stack, prepare arguments
2. `aes128_encrypt()`: 
   - Key expansion (taint spreads to round keys)
   - 10 rounds of encryption (taint spreads through state)
3. Infinite loop (done)

## Expected Taint Propagation

```
aes_key (16 bytes, tainted)
    │
    ▼
key_expansion()
    ├── memcpy key → round_keys[0:15]   (tainted)
    ├── sbox[tainted_index]             (spreads taint)
    └── XOR operations                  (propagates taint)
    │
    ▼
round_keys[0:175] (all tainted)
    │
    ▼
add_round_key() ──► state XOR tainted_key = tainted_state
    │
    ▼
sub_bytes() ──► sbox[tainted_state] = tainted
    │
    ▼
shift_rows() ──► permute(tainted) = tainted
    │
    ▼
mix_columns() ──► GF_mul(tainted) = tainted (spreads across column)
    │
    ▼
(repeat 10 rounds)
    │
    ▼
ciphertext (16 bytes, fully tainted)
```

## Ibex Pipeline Observation

With CellIFT, you should observe taint in:

1. **Register File**: Registers holding key bytes, indices, intermediate values
2. **ALU**: XOR, shifts, arithmetic for GF multiplication
3. **Load/Store Unit**: Memory accesses for key, S-box, state
4. **Data memory**: Key storage, S-box lookups, output buffer

## Comparison with CVA6 Scenario

| Aspect | Ibex | CVA6 |
|--------|------|------|
| ISA | RV32IMC | RV64GC |
| Pipeline | 2-stage in-order | 6-stage out-of-order |
| MMU | None | Sv39 |
| Privilege | M-mode only | M/S/U modes |
| Complexity | Simpler taint paths | More complex propagation |
