#!/usr/bin/env bash
#
# run_vanilla_sim.sh — Standalone vanilla VCD generation for Ibex.
#
# Usage:
#   ./run_vanilla_sim.sh [SIMLEN] [TRACEFILE] [SCENARIO]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIMLEN="${1:-3000}"
TRACEFILE="${2:-${SCRIPT_DIR}/traces/vanilla_aes.vcd}"
SCENARIO="${3:-scenario_aes128_key1}"

ENV_SH="/mnt/nvme1n1p1/cellift-meta-leakage/env.sh"
SIM_BIN="${SCRIPT_DIR}/build/run_vanilla_trace_0.1/default-verilator/Vibex_tiny_soc"
ELF="${SCRIPT_DIR}/sw/${SCENARIO}/build/app.elf"

for f in "$ENV_SH" "$SIM_BIN" "$ELF"; do
    if [[ ! -f "$f" ]]; then
        echo "ERROR: required file not found: $f"
        exit 1
    fi
done

mkdir -p "$(dirname "$TRACEFILE")"

source "$ENV_SH"

echo "=== Ibex Vanilla Simulation ==="
echo "  SCENARIO  : ${SCENARIO}"
echo "  SIMLEN    : ${SIMLEN} cycles"
echo "  ELF       : ${ELF}"
echo "  TRACEFILE : ${TRACEFILE}"
echo ""

SIMLEN="$SIMLEN" \
TRACEFILE="$TRACEFILE" \
SIMROMELF="$ELF" \
SIMSRAMELF="$ELF" \
"$SIM_BIN" 2>&1 | grep -Ev "Writing ELF word|Bank[[:space:]]+[0-9]+: loading addr/wbytes|Adding taint word SRAM addr" || true

echo ""
echo "VCD written: ${TRACEFILE}"
