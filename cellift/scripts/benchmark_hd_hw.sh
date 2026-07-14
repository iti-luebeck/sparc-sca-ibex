#!/usr/bin/env bash
#
# benchmark_hd_hw.sh — Measure HD/HW overhead on Ibex + Kyber workload.
#
# Builds and times four simulator variants (all -O2, no --trace):
#   vanilla_bench            — unmodified Ibex (baseline)
#   cellift_bench_taint_only — CellIFT taint propagation, no HD/HW counter RTL
#   cellift_bench_nocsv      — CellIFT taint + HD/HW counter RTL, no CSV output
#   cellift_bench_csv        — CellIFT taint + HD/HW counter RTL, CSV per cycle
#
# Overhead decomposition:
#   taint propagation  = taint_only / vanilla      - 1
#   HD/HW counter RTL  = nocsv     / taint_only    - 1
#   CSV logging        = csv       / nocsv          - 1
#   total              = csv       / vanilla        - 1
#
# Usage (run from designs/ibex/cellift/ inside the Docker container):
#   ./scripts/benchmark_hd_hw.sh [options]
#
# Options:
#   --simlen N    Simulation cycles per run (default: 2000000)
#   --runs N      Timed repetitions per variant (default: 3)
#   --scenario S  Scenario directory name under sw/ (default: multi_kyber_unmasked_a_000)
#   --no-build    Skip simulator build step (assume binaries already exist)
#   -h, --help    Show this help

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CELLIFT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$CELLIFT_DIR"

# ── Defaults ────────────────────────────────────────────────────────────────
SIMLEN=2000000
RUNS=3
SCENARIO="multi_kyber_unmasked_a_000"
NO_BUILD=0

usage() {
    sed -n '/^# Usage/,/^[^#]/p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --simlen)   SIMLEN="$2";   shift 2 ;;
        --runs)     RUNS="$2";     shift 2 ;;
        --scenario) SCENARIO="$2"; shift 2 ;;
        --no-build) NO_BUILD=1;    shift   ;;
        -h|--help)  usage ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# ── Paths ────────────────────────────────────────────────────────────────────
TOP_EXECUTABLE_NAME="Vibex_tiny_soc"
SIM_VANILLA="build/run_vanilla_bench_0.1/default-verilator/${TOP_EXECUTABLE_NAME}"
SIM_TAINT_ONLY="build/run_cellift_bench_taint_only_0.1/default-verilator/${TOP_EXECUTABLE_NAME}"
SIM_NOCSV="build/run_cellift_bench_nocsv_0.1/default-verilator/${TOP_EXECUTABLE_NAME}"
SIM_CSV="build/run_cellift_bench_csv_0.1/default-verilator/${TOP_EXECUTABLE_NAME}"

SW_DIR="sw/${SCENARIO}"
ELF="${SW_DIR}/build/app.elf"
TAINT="taint_data/${SCENARIO}/taint_data.txt"

RESULTS_DIR="results"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
REPORT="${RESULTS_DIR}/benchmark_hd_hw_${TIMESTAMP}.txt"

# ── Helpers ──────────────────────────────────────────────────────────────────
banner() { echo; echo "===================================================="; printf "  %s\n" "$1"; echo "===================================================="; }
die()    { echo "ERROR: $*" >&2; exit 1; }

# Returns the median of a space-separated list of numbers (bash + awk).
median() {
    echo "$@" | tr ' ' '\n' | sort -n | awk '
        { vals[NR] = $1 }
        END {
            n = NR
            if (n % 2 == 1) print vals[(n+1)/2]
            else printf "%.3f\n", (vals[n/2] + vals[n/2+1]) / 2.0
        }'
}

# Time a single simulator run; echo elapsed seconds to stdout.
time_run() {
    local sim="$1"; shift
    local start end
    start=$(date +%s%N)
    "$sim" "$@" > /dev/null 2>&1
    end=$(date +%s%N)
    awk -v s="$start" -v e="$end" 'BEGIN { printf "%.3f\n", (e - s) / 1e9 }'
}

# ── Preflight checks ─────────────────────────────────────────────────────────
banner "Preflight"

[[ "${CELLIFT_ENV_SOURCED:-}" == "yes" ]] || \
    die "CELLIFT_ENV_SOURCED not set. Source env.sh or run inside the Docker container."

# Compile firmware if ELF is missing.
if [[ ! -f "$ELF" ]]; then
    echo "ELF not found; compiling ${SCENARIO}..."
    make -C "$SW_DIR" -j"${CELLIFT_JOBS:-$(nproc)}"
fi

[[ -f "$ELF" ]]   || die "ELF still missing after compile: ${ELF}"
[[ -f "$TAINT" ]] || die "Taint file not found: ${TAINT}"

echo "  scenario : ${SCENARIO}"
echo "  simlen   : ${SIMLEN} cycles"
echo "  runs     : ${RUNS}"
echo "  ELF      : ${ELF}"
echo "  taint    : ${TAINT}"

# ── Build simulators ─────────────────────────────────────────────────────────
if [[ $NO_BUILD -eq 0 ]]; then
    banner "Building benchmark simulators"
    make build-bench-sims
else
    echo "(--no-build: skipping simulator build)"
fi

for sim in "$SIM_VANILLA" "$SIM_TAINT_ONLY" "$SIM_NOCSV" "$SIM_CSV"; do
    [[ -f "$sim" ]] || die "Simulator binary not found: ${sim}"
done

# ── Run timings ──────────────────────────────────────────────────────────────
banner "Running benchmarks (${RUNS} run(s) each)"

# Common env for all runs.
export SIMLEN SIMROMELF="$ELF" SIMSRAMELF="$ELF" SIMROMTAINT="$TAINT" SIMSRAMTAINT="$TAINT"

declare -A TIMES_ALL
TMPCSV="$(mktemp /tmp/bench_hdhw_XXXXXX.csv)"
trap 'rm -f "$TMPCSV"' EXIT

for VARIANT in vanilla_bench cellift_bench_taint_only cellift_bench_nocsv cellift_bench_csv; do
    case "$VARIANT" in
        vanilla_bench)            SIM="$SIM_VANILLA"    ;;
        cellift_bench_taint_only) SIM="$SIM_TAINT_ONLY" ;;
        cellift_bench_nocsv)      SIM="$SIM_NOCSV"      ;;
        cellift_bench_csv)        SIM="$SIM_CSV"         ;;
    esac

    SAMPLES=()
    printf "  %-32s " "$VARIANT"
    for i in $(seq 1 "$RUNS"); do
        if [[ "$VARIANT" == "cellift_bench_csv" ]]; then
            export CSVFILE="$TMPCSV"
        else
            unset CSVFILE 2>/dev/null || true
        fi
        T=$(time_run "$SIM")
        SAMPLES+=("$T")
        printf "%.3fs " "$T"
    done
    echo
    TIMES_ALL[$VARIANT]="$(median "${SAMPLES[@]}")"
done

# ── Compute overhead ─────────────────────────────────────────────────────────
T_VAN="${TIMES_ALL[vanilla_bench]}"
T_TAINT="${TIMES_ALL[cellift_bench_taint_only]}"
T_NOCSV="${TIMES_ALL[cellift_bench_nocsv]}"
T_CSV="${TIMES_ALL[cellift_bench_csv]}"

overhead_pct() {
    awk -v a="$1" -v b="$2" 'BEGIN { printf "%+.1f%%", (a/b - 1.0) * 100.0 }'
}

CPS_VAN=$(awk   -v s="$SIMLEN" -v t="$T_VAN"   'BEGIN { printf "%d", s/t }')
CPS_TAINT=$(awk -v s="$SIMLEN" -v t="$T_TAINT" 'BEGIN { printf "%d", s/t }')
CPS_NOCSV=$(awk -v s="$SIMLEN" -v t="$T_NOCSV" 'BEGIN { printf "%d", s/t }')
CPS_CSV=$(awk   -v s="$SIMLEN" -v t="$T_CSV"   'BEGIN { printf "%d", s/t }')

OVH_TAINT=$(overhead_pct "$T_TAINT" "$T_VAN")    # taint propagation only
OVH_HDHW=$(overhead_pct  "$T_NOCSV" "$T_TAINT")  # HD/HW counter RTL (vs taint-only)
OVH_IO=$(overhead_pct    "$T_CSV"   "$T_NOCSV")   # CSV I/O (vs full RTL, no output)
OVH_TOTAL=$(overhead_pct "$T_CSV"   "$T_VAN")     # total end-to-end

# ── Report ───────────────────────────────────────────────────────────────────
mkdir -p "$RESULTS_DIR"

{
printf '\n'
printf '=======================================================\n'
printf '  Ibex + Kyber HD/HW Overhead Benchmark\n'
printf '  scenario : %s\n' "$SCENARIO"
printf '  simlen   : %d cycles\n' "$SIMLEN"
printf '  runs     : %d  (median shown)\n' "$RUNS"
printf '  date     : %s\n' "$(date -Iseconds)"
printf '=======================================================\n\n'
printf '%-32s | %10s | %12s | %s\n' "Variant" "Median (s)" "Cycles/s" "Overhead"
printf '%s\n' "$(printf -- '-%.0s' {1..85})"
printf '%-32s | %10s | %12s | %s\n' "vanilla_bench"            "$T_VAN"   "$CPS_VAN"   "— (baseline)"
printf '%-32s | %10s | %12s | %s\n' "cellift_bench_taint_only" "$T_TAINT" "$CPS_TAINT" "${OVH_TAINT}  vs baseline  (taint propagation)"
printf '%-32s | %10s | %12s | %s\n' "cellift_bench_nocsv"      "$T_NOCSV" "$CPS_NOCSV" "${OVH_HDHW}  vs taint-only  (HD/HW counter RTL)"
printf '%-32s | %10s | %12s | %s\n' "cellift_bench_csv"        "$T_CSV"   "$CPS_CSV"   "${OVH_IO}  vs nocsv  (CSV logging)"
printf '\n'
printf 'Overhead decomposition:\n'
printf '  Taint propagation (CellIFT base):  %s\n' "$OVH_TAINT"
printf '  HD/HW counter RTL (leakage DFFs):  %s\n' "$OVH_HDHW"
printf '  CSV logging (per-cycle I/O):        %s\n' "$OVH_IO"
printf '  ─────────────────────────────────────\n'
printf '  Total HD/HW pipeline overhead:     %s\n\n' "$OVH_TOTAL"
} | tee "$REPORT"

echo "Report saved: ${REPORT}"
