# Tiny AI Tainted Weights Scenario

This scenario runs a minimal neural network inference on the Ibex core,
with the network weights marked as tainted in CellIFT.

## Network Architecture

```
Input (4) --> Hidden (8, ReLU) --> Output (3)
```

- **Input layer**: 4 neurons (features/sensor values)
- **Hidden layer**: 8 neurons with ReLU activation
- **Output layer**: 3 neurons (classification scores)

## Tainted Data

The following are marked as tainted (secret model weights):

| Data | Size | Description |
|------|------|-------------|
| `weights_ih` | 64 bytes | Input-to-hidden weights (8×4 matrix) |
| `bias_h` | 16 bytes | Hidden layer biases (8 values) |
| `weights_ho` | 48 bytes | Hidden-to-output weights (3×8 matrix) |
| `bias_o` | 8 bytes | Output layer biases (3 values + padding) |
| **Total** | **136 bytes** | All network parameters |

## Fixed-Point Arithmetic

Uses Q8.8 format (8 integer bits, 8 fractional bits):
- Range: -128.0 to +127.996
- Resolution: 1/256 ≈ 0.0039

## Building

```bash
cd /path/to/cellift-ibex/cellift
source ../env.sh  # Set up RISC-V toolchain

cd sw/scenario_tinyai_tainted_weights
make
```

## Running CellIFT Simulation

```bash
# From cellift directory
source env_tinyai.sh
make run_cellift_trace_fst
```

## Taint Observation

CellIFT will track how the tainted weights propagate through:

1. **Matrix multiplication**: `weights × input` in each layer
2. **Bias addition**: Tainted biases added to activations
3. **Activation function**: ReLU applied to tainted values
4. **Final output**: Classification scores are fully tainted

## Files

- `tinyai.c` - Neural network implementation
- `main.S` - Entry point, weight data definitions
- `link.ld` - Linker script with tainted section
- `Makefile` - Build system
