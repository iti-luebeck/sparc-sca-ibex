# AES-128 Masked Key Scenario (Key 2) for CellIFT - Ibex Core

This scenario demonstrates a **toy masked AES-128** implementation for
information-flow tracking using CellIFT on the Ibex (RV32IMC) processor.

> Note: The masking used here is **deterministic and simplified** for
> experimentation. It is **not** a production-grade side-channel countermeasure.

## Purpose

Observe how taint propagates when the AES key is stored as two shares:

- `key_share0` (tainted)
- `key_mask` (not tainted)

The actual key is reconstructed by XORing the two shares. The AES state is kept
masked during rounds using a per-byte `state_mask`.

## Architecture

- **Core**: Ibex (RV32IMC)
- **Mode**: Machine mode only (no MMU/virtual memory)
- **Memory**: Simple flat memory model starting at 0x80

## Files

| File | Description |
|------|-------------|
| `main.S` | Entry point, data definitions, calls masked AES |
| `aes128_masked.c` | Masked AES-128 implementation in C |
| `link.ld` | Linker script with tainted section |
| `Makefile` | Build configuration |

## Memory Layout

```
0x00000080  .text.init    (entry point)
0x00000180  .text         (AES code)
0x00000280  .rodata       (S-box table)
0x00000380  .data         (plaintext, masks, context)
0x00000480  .bss
0x00000580  stack
0x00000C00  .tainted_data (key_share0 - TAINT THIS!)
```

## Taint Configuration

In CellIFT simulation, mark the following as tainted:

- **Address**: `0xC00`
- **Size**: 16 bytes (`key_share0`)
- **Label**: `aes_key_share0`

## Building

```bash
make clean
make
```

Outputs:
- `build/app.elf` - Executable
- `build/app.elf.dump` - Disassembly

## Test Vectors

| Data | Value |
|------|-------|
| Key | `fffefdfcfbfaf9f8f7f6f5f4f3f2f1f0` |
| Plaintext | `3243f6a8885a308d313198a2e0370734` |
| Ciphertext | `3925841d02dc09fbdc118597196a0b32` |

## Expected Taint Propagation

```
key_share0 (tainted)  key_mask (clean)
        \                /
         \              /
           key = share0 ^ mask   (tainted)
                    |
                    v
               key_expansion()   (round keys tainted)
                    |
                    v
masked state = plaintext ^ state_mask
                    |
                    v
sub_bytes_masked() / shift_rows_pair() / mix_columns_masked()
                    |
                    v
ciphertext (unmasked, tainted)
```

## Ibex Pipeline Observation

With CellIFT, you should observe taint in:

1. **Register File**: registers holding reconstructed key, state bytes
2. **ALU**: XORs for masking/unmasking and key reconstruction
3. **Load/Store Unit**: memory accesses for key shares, masks, and state
4. **Data memory**: expanded key schedule and output buffer
