#!/usr/bin/env bash
#
# run_cellift_sim.sh — Standalone CellIFT VCD generation for Ibex.
#
# Usage:
#   ./run_cellift_sim.sh [SIMLEN] [TRACEFILE] [SCENARIO]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIMLEN="${1:-3000}"
TRACEFILE="${2:-${SCRIPT_DIR}/traces/cellift_aes.vcd}"
SCENARIO="${3:-scenario_aes128_key1}"

: "${SPARC_SCA_ROOT:=$(cd "${SCRIPT_DIR}/../../.." && pwd)}"
ENV_SH="${SPARC_SCA_ROOT}/env.sh"
# fasttrace, not trace: both targets pass identical Verilator trace flags, so
# the VCD is byte-for-byte equivalent -- they differ only in host g++ opt
# level (-O2 vs -g -O0). Attribution runs this in bulk, so -O0 was pure loss.
SIM_BIN="${SCRIPT_DIR}/build/run_cellift_fasttrace_0.1/default-verilator/Vibex_tiny_soc"
ELF="${SCRIPT_DIR}/sw/${SCENARIO}/build/app.elf"
TAINT="${SCRIPT_DIR}/taint_data/${SCENARIO}/taint_data.txt"

for f in "$SIM_BIN" "$ELF" "$TAINT"; do
    if [[ ! -f "$f" ]]; then
        echo "ERROR: required file not found: $f"
        exit 1
    fi
done

mkdir -p "$(dirname "$TRACEFILE")"

if [[ "${CELLIFT_ENV_SOURCED:-}" != "yes" ]]; then
    source "$ENV_SH"
fi

echo "=== Ibex CellIFT Simulation ==="
echo "  SCENARIO  : ${SCENARIO}"
echo "  SIMLEN    : ${SIMLEN} cycles"
echo "  ELF       : ${ELF}"
echo "  TAINT     : ${TAINT}"
echo "  TRACEFILE : ${TRACEFILE}"
echo ""

SIMLEN="$SIMLEN" \
TRACEFILE="$TRACEFILE" \
SIMROMELF="$ELF" \
SIMSRAMELF="$ELF" \
SIMROMTAINT="$TAINT" \
SIMSRAMTAINT="$TAINT" \
"$SIM_BIN" 2>&1 | grep -Ev "Writing ELF word|Bank[[:space:]]+[0-9]+: loading addr/wbytes|Adding taint word SRAM addr" || true

echo ""
echo "VCD written: ${TRACEFILE}"
