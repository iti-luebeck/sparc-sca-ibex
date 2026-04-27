#!/usr/bin/env bash
#
# build_fasttrace_sim.sh - Build the standalone run_cellift_fasttrace simulator.
#
# Usage:
#   ./build_fasttrace_sim.sh [--force]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FT_DIR="${SCRIPT_DIR}/build/run_cellift_fasttrace_0.1/default-verilator"
FT_BIN="${FT_DIR}/Vibex_tiny_soc"
IBEX_CORES_ROOT="${SCRIPT_DIR}/.."
OPENTITAN_HW_ROOT="/mnt/nvme1n1p1/cellift-meta-leakage/external-dependencies/cellift-opentitan/hw"
FORCE_REBUILD=0

if [[ "${1:-}" == "--force" ]]; then
    FORCE_REBUILD=1
elif [[ $# -gt 0 ]]; then
    echo "ERROR: unknown option: $1"
    echo "Usage: $0 [--force]"
    exit 1
fi

needs_rebuild=1
if [[ -x "${FT_BIN}" && "${FORCE_REBUILD}" -eq 0 ]]; then
    needs_rebuild=0
    while IFS= read -r src; do
        if [[ "$src" -nt "${FT_BIN}" ]]; then
            needs_rebuild=1
            echo "Rebuild needed: ${src} is newer than ${FT_BIN}"
            break
        fi
    done < <(find "${SCRIPT_DIR}/dv" "${SCRIPT_DIR}/src" -type f \( -name '*.cc' -o -name '*.cpp' -o -name '*.h' -o -name '*.sv' \) | sort)
fi

if [[ "${needs_rebuild}" -eq 0 ]]; then
    echo "fasttrace simulator up to date: ${FT_BIN}"
    exit 0
fi

if [[ "${FORCE_REBUILD}" -eq 1 ]]; then
    echo "Force rebuild requested for standalone fasttrace simulator."
fi
echo "Building standalone fasttrace simulator via FuseSoC..."
source /mnt/nvme1n1p1/cellift-meta-leakage/env.sh >/dev/null 2>&1
fusesoc \
    --cores-root="${SCRIPT_DIR}" \
    --cores-root="${IBEX_CORES_ROOT}" \
    --cores-root="${OPENTITAN_HW_ROOT}" \
    run --build run_cellift_fasttrace

if [[ ! -x "${FT_BIN}" ]]; then
    echo "ERROR: FuseSoC build did not produce ${FT_BIN}"
    exit 1
fi

echo "fasttrace simulator built via FuseSoC: ${FT_BIN}"
