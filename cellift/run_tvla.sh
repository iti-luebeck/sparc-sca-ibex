#!/usr/bin/env bash
#
# run_tvla.sh — Single-pair TVLA smoke check for CellIFT Ibex.
#
# Usage:
#   ./run_tvla.sh [SIMLEN] [OUTDIR] [SCENARIO_A] [SCENARIO_B] [--plot]
#
# Defaults:
#   SIMLEN     = 3000
#   OUTDIR     = results/smoke_tvla
#   SCENARIO_A = scenario_aes128_key1
#   SCENARIO_B = scenario_aes128_key2

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SIMLEN="${1:-3000}"
OUTDIR="${2:-${SCRIPT_DIR}/results/smoke_tvla}"
SCENARIO_A="${3:-scenario_aes128_key1}"
SCENARIO_B="${4:-scenario_aes128_key2}"
shift 4 2>/dev/null || true

: "${SPARC_SCA_ROOT:=$(cd "${SCRIPT_DIR}/../../.." && pwd)}"
ENV_SH="${SPARC_SCA_ROOT}/env.sh"
CSV_BIN="${SCRIPT_DIR}/build/run_cellift_csvlog_0.1/default-verilator/Vibex_tiny_soc"

ELF_A="${SCRIPT_DIR}/sw/${SCENARIO_A}/build/app.elf"
ELF_B="${SCRIPT_DIR}/sw/${SCENARIO_B}/build/app.elf"
TAINT_A="${SCRIPT_DIR}/taint_data/${SCENARIO_A}/taint_data.txt"
TAINT_B="${SCRIPT_DIR}/taint_data/${SCENARIO_B}/taint_data.txt"

CSV_A="${OUTDIR}/group_a.csv"
CSV_B="${OUTDIR}/group_b.csv"

if [[ ! "$SIMLEN" =~ ^[0-9]+$ ]] || [[ "$SIMLEN" -lt 1 ]]; then
    echo "ERROR: SIMLEN must be a positive integer (got '${SIMLEN}')"
    exit 1
fi

if [[ "${CELLIFT_ENV_SOURCED:-}" != "yes" ]]; then
    source "$ENV_SH"
fi

for f in "$CSV_BIN" "$ELF_A" "$ELF_B" "$TAINT_A" "$TAINT_B"; do
    if [[ ! -f "$f" ]]; then
        echo "ERROR: required file not found: $f"
        exit 1
    fi
done

mkdir -p "$OUTDIR"

echo "════════════════════════════════════════════════════════════"
echo "  CellIFT Single-Pair TVLA Smoke Check"
echo "  Group A     : ${SCENARIO_A}"
echo "  Group B     : ${SCENARIO_B}"
echo "  SIMLEN      : ${SIMLEN}"
echo "  Output dir  : ${OUTDIR}"
echo "════════════════════════════════════════════════════════════"
echo ""

echo "[A] Running CSV simulation: ${SCENARIO_A}"
SIMLEN="$SIMLEN" \
TRACEFILE=/dev/null \
CSVFILE="$CSV_A" \
SIMROMELF="$ELF_A" \
SIMSRAMELF="$ELF_A" \
SIMROMTAINT="$TAINT_A" \
SIMSRAMTAINT="$TAINT_A" \
"$CSV_BIN" 2>&1 | grep -Ev "Writing ELF word|Bank[[:space:]]+[0-9]+: loading addr/wbytes|Adding taint word SRAM addr" || true

echo "[B] Running CSV simulation: ${SCENARIO_B}"
SIMLEN="$SIMLEN" \
TRACEFILE=/dev/null \
CSVFILE="$CSV_B" \
SIMROMELF="$ELF_B" \
SIMSRAMELF="$ELF_B" \
SIMROMTAINT="$TAINT_B" \
SIMSRAMTAINT="$TAINT_B" \
"$CSV_BIN" 2>&1 | grep -Ev "Writing ELF word|Bank[[:space:]]+[0-9]+: loading addr/wbytes|Adding taint word SRAM addr" || true

echo ""
echo "Running TVLA analysis..."
python3 "${SCRIPT_DIR}/tvla_analysis.py" "$CSV_A" "$CSV_B" --out "${OUTDIR}/tvla" "$@"

echo ""
echo "Done."
echo "  Group A CSV : ${CSV_A}"
echo "  Group B CSV : ${CSV_B}"
