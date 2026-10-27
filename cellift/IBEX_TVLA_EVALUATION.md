# Ibex CellIFT TVLA Evaluation (Core Pipeline)

Authoritative guide for the Ibex CellIFT workflow in this directory:
designs/ibex/cellift

## 1) Environment Setup

cd designs/ibex/cellift
. env.sh
make installrequirements

Core simulation binaries used by this pipeline:

- build/run_cellift_csvlog_0.1/default-verilator/Vibex_tiny_soc
- build/run_cellift_fasttrace_0.1/default-verilator/Vibex_tiny_soc
- build/run_vanilla_trace_0.1/default-verilator/Vibex_tiny_soc

If missing, build CSV logger with:

./build_csvlog_sim.sh --force

## 2) Ibex vs Proteus (Condensed)

- Ibex top-level simulator binary is Vibex_tiny_soc.
- Ibex simulations use ROM and SRAM ELF variables:
  - SIMROMELF, SIMSRAMELF
- CellIFT runs also require ROM/SRAM taint variables:
  - SIMROMTAINT, SIMSRAMTAINT
- TVLA counters exported by Ibex CSV logger (dv/toplevel_csv.cc):
  - leakage_counter_t0
  - hamming_weight_counter_t0
  - hamming_distance_counter_t0

## 3) Core Entry Point

Run the complete evaluation with:

./run_full_evaluation.sh --plot

This executes the full 10-step flow (generation, compile, multi-trace TVLA,
root-cause signal/instruction mapping, pass-2 quantification, manifest, report,
and publication summary).

## 4) Full Option Reference (run_full_evaluation.sh)

Usage:
  ./run_full_evaluation.sh [options]

Options:
  --workload NAME        Workload profile for scenario generation (default: aes)
  --n-unmasked N         Traces/group for unmasked run (default: 20)
  --n-masked N           Traces/group for masked run (default: 100)
  --simlen N             Simulation cycles per trace (default: 30000)
  --seed N               Matched-pairs seed (default: 42)
  --jobs N               Parallel workers for simulations (default: CPU count)
  --results DIR          Output root directory (default: ./results)
  --threshold T          Welch |t| threshold (default: 4.5)
  --window-len N         Fallback cycles after first leak if region selection empty (default: 5)
  --attr-cycles-max N    Max diversified attribution cycles for root-cause mapping (default: 24)
  --interval-top-k N     Top-K annotated intervals per counter (default: 8)
  --plot                 Enable dashboard/episode plots
  --no-interval-plots    Disable annotated interval plots
  --skip-preflight       Skip preflight checks
  --skip-gen             Skip scenario generation
  --skip-compile         Skip scenario compilation
  -h, --help             Show help

Minimal smoke run example:

./run_full_evaluation.sh --n-unmasked 2 --n-masked 2 --simlen 3000 --plot

## 5) Pipeline Steps Actually Run (10 Steps)

run_full_evaluation.sh runs:

1. Preflight (run_eval_preflight.sh)
2. Scenario generation (gen_scenarios.py)
3. Scenario compilation (compile_scenarios.sh)
4. Multi-trace TVLA (run_multi_trace_tvla.sh + multi_tvla_driver.py)
5. Region discovery pass 1 (cycle_leakage_quantifier.py)
6. Root-cause (unmasked) (run_signal_correlation.sh)
7. Root-cause (masked) (run_signal_correlation.sh)
8. Quantification pass 2 + interval annotations (cycle_leakage_quantifier.py)
9. Run manifest export (run_manifest_refined.json + compatibility copy)
10. Root-cause report + publication summary (generate_root_cause_report.py, generate_publication_summary.py)

## 6) Output Layout

Default root: results/ (or --results DIR).

- results/unmasked/
  - group_a_*.csv, group_b_*.csv
  - welch_summary.txt
  - signals_refined_signals.json, signals_refined_instructions.json
  - signals_refined_heatmap.png, signals_refined_timeline.png
  - leakage_regions.json, leakage_regions.csv
  - leakage_*_interval_*_annotated.png (if interval plotting enabled)
- results/masked/
  - same structure as unmasked
- results/run_manifest_refined.json and results/run_manifest.json
- results/root_cause_report_refined.md and .json
- results/root_cause_report.md and .json (compatibility copies)
- results/publication_summary_refined.md and .json

## 7) AES Scenarios Used

Reference scenario names (kept in sw/):

- scenario_aes128_key1
- scenario_aes128_key2
- scenario_aes128_masked_key1
- scenario_aes128_masked_key2

Generated matched-pair prefixes:

- multi_aes_unmasked_a_###, multi_aes_unmasked_b_###
- multi_aes_masked_a_###, multi_aes_masked_b_###

Manifests are written to:

- sw/_manifests/multi_aes_unmasked_a_manifest.json
- sw/_manifests/multi_aes_unmasked_b_manifest.json
- sw/_manifests/multi_aes_masked_a_manifest.json
- sw/_manifests/multi_aes_masked_b_manifest.json

## 8) Root-Cause and Instruction Mapping

Root-cause stage is driven by:

- run_signal_correlation.sh
- leakage_signals.py
- pc_at_leakage.py

Flow:

1. Generate CellIFT VCD for Group A and B at focused attribution cycles.
2. Rank divergent signals per leakage cycle.
3. Generate vanilla VCD for clean instruction/PC extraction.
4. Map leakage cycles to PCs and source lines.

## 9) Kept Core Scripts (Current Inventory)

Top-level scripts used in the Ibex flow:

- run_full_evaluation.sh
- run_eval_preflight.sh
- build_csvlog_sim.sh
- gen_scenarios.py
- compile_scenarios.sh
- run_tvla.sh
- run_multi_trace_tvla.sh
- multi_tvla_driver.py
- tvla_analysis.py
- run_cellift_sim.sh
- run_vanilla_sim.sh
- run_signal_correlation.sh
- leakage_signals.py
- pc_at_leakage.py
- cycle_leakage_quantifier.py
- generate_root_cause_report.py
- generate_publication_summary.py
- hw_model_test.py

## 10) Current Status and Known Notes

Current practical status in this workspace:

- CSV logging path is operational.
- Single-pair TVLA smoke checks are operational (run_tvla.sh).
- Multi-trace Welch TVLA requires at least 2 traces per group.
- hw_model_test.py requires a 256-case sweep with files:
  - group_a_000.csv ... group_a_255.csv
  - group_b_000.csv ... group_b_255.csv

Known notes:

- Keep simulation binaries rebuilt if hierarchy or core files change.
- TVLA summary interpretation is driven by welch_summary.txt fields:
  - first_leaky_cycle
  - leaky_cycle_count
  - max_t (where Welch applies)
- For deterministic smoke checks, N=1 can validate mechanics but is not
  sufficient for Welch inference.

## Quick Script Checks

Single-pair TVLA smoke check:

bash run_tvla.sh 3000 results/smoke_tvla scenario_aes128_key1 scenario_aes128_key2 --plot

Standalone CellIFT VCD:

bash run_cellift_sim.sh 3000 /tmp/test_cellift.vcd scenario_aes128_key1

Standalone vanilla VCD:

bash run_vanilla_sim.sh 3000 /tmp/test_vanilla.vcd scenario_aes128_key1

HW-model script interface check:

python3 hw_model_test.py --help
