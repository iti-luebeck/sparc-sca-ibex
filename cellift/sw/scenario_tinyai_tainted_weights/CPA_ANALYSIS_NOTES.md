# CPA Attack Analysis Notes

## Summary

The CPA (Correlation Power Analysis) attack was set up to attempt recovery of neural network weights from side-channel traces. While the infrastructure is working, the attack results are limited by fundamental constraints.

## Key Findings

### 1. Trace Generation Fixed
The original issue was that all VCD traces were identical because `generate_scenario.py` had a bug in the `update_main_asm()` function. The regex pattern:
```python
# Old (broken): r'(\.globl input_samples\ninput_samples:\n)(.*?)(\/\*\s*Output scores)'
# New (fixed):  r'(\.globl input_samples\ninput_samples:\n)(.*?)(\n\/\*\n \* Output scores)'
```

After fixing, all 5 VCD traces are now properly different (176,207 lines differ between traces).

### 2. WAL++ HD/HW Analysis
The WAL++ analysis now produces different CSV files for each trace, with significant variance:
- Non-zero variance cycles: 4401/15004 (29%)
- Maximum variance: 356,781
- High-variance cycles correspond to data-dependent operations

### 3. CPA Attack Limitations

#### Problem 1: Aggregated Power Model
The WAL++ `--fast-hd-all` sums Hamming Distance across ALL signals at each cycle. This makes it impossible to isolate individual weight operations.

#### Problem 2: Indistinguishable Neurons
All 8 neurons process the same 4 input samples. The hypothetical power model `HW(input[i] * weight_guess)` produces the same values for all neurons at a given input index. This is why the attack recovers the same values for all 8 neurons.

#### Problem 3: Too Few Traces
With only 5 traces, CPA cannot reliably distinguish true correlations from noise. High correlations (>0.97) can occur by chance with 5 data points.

#### Problem 4: Time Point Selection
The attack searches across all 15,004 time points for maximum correlation. Without knowing the specific cycles when each weight is used, the attack finds spurious correlations.

## Results

The attack recovered: `[28, -196, 20, -244]` for all neurons (identical)

True weight column sums:
- Input 0: 64 (recovered ~28)
- Input 1: 208 (recovered ~-196)
- Input 2: 320 (recovered ~20)
- Input 3: 96 (recovered ~-244)

The correlations are very high (0.99+) but the values don't match, indicating the model is correlating with the wrong quantity.

## Recommendations for Improved Attack

1. **More traces**: Generate 100+ test cases for statistically significant results
2. **Per-signal traces**: Use WAL++ `--fast-hd-signals` with specific register signals
3. **POI identification**: Identify specific cycles when each weight is used
4. **Different power model**: Consider using intermediate computation results, not just input×weight
5. **Longer simulations**: Ensure the inference actually completes (may need >5000 cycles)

## Files Created
- `cpa_attack.py` - CPA attack implementation
- `cpa_results/` - Attack results directory
  - `attack_results.json` - Full results in JSON
  - `correlation_heatmap.png` - Visualization
  - `plots/` - Per-weight correlation curves

## Date
Generated: 2025-01-20
