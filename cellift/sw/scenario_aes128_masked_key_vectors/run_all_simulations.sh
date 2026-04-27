#!/bin/bash
#
# Run all AES-128 masked vector simulations in parallel (Ibex)
#
# Usage:
#   ./run_all_simulations.sh                    # Run all vanilla sims
#   ./run_all_simulations.sh --single 5         # Run only vector 5
#   ./run_all_simulations.sh --range 0 9        # Run vectors 0-9
#   ./run_all_simulations.sh --simlen 3500      # Custom cycle count
#   ./run_all_simulations.sh --jobs 8           # Run 8 simulations in parallel
#   ./run_all_simulations.sh --cellift          # Run CellIFT (FST) sims

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration
MANIFEST="$SCRIPT_DIR/test_patterns/manifest.txt"
NUM_VECTORS=1000
SIMLEN=18000
#TRACE_DIR="$SCRIPT_DIR/traces"
TRACE_DIR="/home/andrija/rackstation_home/CellIFT_traces/ibex_masked_aes/vcds"

BUILD_DIR="$SCRIPT_DIR/build"
MAX_JOBS=$(nproc 2>/dev/null || echo 4)

if [ -f "$MANIFEST" ]; then
    NUM_VECTORS=$(wc -l < "$MANIFEST")
fi

# Paths to simulators
CELLIFT_IBEX_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
VANILLA_SIM="$CELLIFT_IBEX_DIR/build/run_vanilla_trace_0.1/default-verilator/Vibex_tiny_soc"
CELLIFT_SIM="$CELLIFT_IBEX_DIR/build/run_cellift_trace_fst_0.1/default-verilator/Vibex_tiny_soc"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

STATUS_DIR=$(mktemp -d)
trap "rm -rf $STATUS_DIR" EXIT

mkdir -p "$TRACE_DIR"

run_sim() {
    local idx=$1
    local sim_type=$2

    local sim_bin="$VANILLA_SIM"
    local trace_ext="vcd"

    if [ "$sim_type" = "cellift" ]; then
        sim_bin="$CELLIFT_SIM"
        trace_ext="fst"
    fi

    local padded_idx=$(printf "%04d" $idx)
    local elf_file="$BUILD_DIR/app_${padded_idx}.elf"
    local trace_file="$TRACE_DIR/${sim_type}_${padded_idx}.${trace_ext}"
    local status_file="$STATUS_DIR/status_${padded_idx}"

    if [ ! -f "$elf_file" ]; then
        echo "FAIL:$elf_file not found" > "$status_file"
        return 1
    fi

    if [ ! -f "$sim_bin" ]; then
        echo "FAIL:Simulator not found" > "$status_file"
        return 1
    fi

    SIMROMELF="$elf_file" \
    SIMSRAMELF="$elf_file" \
    TRACEFILE="$trace_file" \
    SIMLEN="$SIMLEN" \
    SIMROMTAINT="/dev/null" \
    SIMSRAMTAINT="/dev/null" \
    "$sim_bin" > /dev/null 2>&1

    if [ -f "$trace_file" ]; then
        local size
        size=$(du -h "$trace_file" | cut -f1)
        echo "OK:$size" > "$status_file"
        return 0
    else
        echo "FAIL:No trace" > "$status_file"
        return 1
    fi
}

export -f run_sim
export VANILLA_SIM CELLIFT_SIM BUILD_DIR TRACE_DIR SIMLEN STATUS_DIR

SIM_TYPE="vanilla"
START_IDX=0
END_IDX=$((NUM_VECTORS - 1))

while [[ $# -gt 0 ]]; do
    case $1 in
        --cellift) SIM_TYPE="cellift"; shift ;;
        --vanilla) SIM_TYPE="vanilla"; shift ;;
        --range) START_IDX=$2; END_IDX=$3; shift 3 ;;
        --single) START_IDX=$2; END_IDX=$2; shift 2 ;;
        --simlen) SIMLEN=$2; export SIMLEN; shift 2 ;;
        --jobs|-j) MAX_JOBS=$2; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --vanilla       Run vanilla simulations (default)"
            echo "  --cellift       Run CellIFT simulations (FST)"
            echo "  --single N      Run only vector N"
            echo "  --range A B     Run vectors A through B"
            echo "  --simlen N      Simulation cycles (default: $SIMLEN)"
            echo "  --jobs N, -j N  Parallel jobs (default: $MAX_JOBS)"
            exit 0 ;;
        *) echo "Unknown: $1"; exit 1 ;;
    esac
done


echo "==============================================="
echo "AES-128 Masked Vector Runner (Ibex, Parallel)"
echo "==============================================="
echo "Build dir: $BUILD_DIR"
echo "Trace dir: $TRACE_DIR"
echo "Parallel jobs: $MAX_JOBS"
echo ""

if [ ! -f "$BUILD_DIR/app_0000.elf" ]; then
    echo -e "${YELLOW}Building executables...${NC}"
    cd "$SCRIPT_DIR" && make
fi

TOTAL=$((END_IDX - START_IDX + 1))
echo "Simulation: $SIM_TYPE, Cycles: $SIMLEN, Vectors: $START_IDX-$END_IDX ($TOTAL total)"
echo ""

RUNNING=0
PIDS=()
COMPLETED=0
START_TIME=$(date +%s)

for i in $(seq $START_IDX $END_IDX); do
    run_sim $i $SIM_TYPE &
    PIDS+=($!)
    RUNNING=$((RUNNING + 1))

    if [ $RUNNING -ge $MAX_JOBS ]; then
        wait -n 2>/dev/null || wait ${PIDS[0]}
        RUNNING=$((RUNNING - 1))
        COMPLETED=$((COMPLETED + 1))
        PERCENT=$((COMPLETED * 100 / TOTAL))
        ELAPSED=$(($(date +%s) - START_TIME))
        printf "\rProgress: %d/%d (%d%%) | Elapsed: %ds | Running: %d jobs" $COMPLETED $TOTAL $PERCENT $ELAPSED $RUNNING
    fi
done

wait

# Wait for remaining jobs to finish and show final progress
while [ $COMPLETED -lt $TOTAL ]; do
    COMPLETED=$((COMPLETED + 1))
    PERCENT=$((COMPLETED * 100 / TOTAL))
    ELAPSED=$(($(date +%s) - START_TIME))
    printf "\rProgress: %d/%d (%d%%) | Elapsed: %ds | Running: 0 jobs" $COMPLETED $TOTAL $PERCENT $ELAPSED
done
echo ""

SUCCESS=0
FAILED=0

echo "Results:"
for i in $(seq $START_IDX $END_IDX); do
    padded_idx=$(printf "%04d" $i)
    status_file="$STATUS_DIR/status_${padded_idx}"
    if [ -f "$status_file" ]; then
        status=$(cat "$status_file")
        if [[ "$status" == OK:* ]]; then
            size="${status#OK:}"
            echo -e "  Vector $i: ${GREEN}OK${NC} ($size)"
            SUCCESS=$((SUCCESS + 1))
        else
            msg="${status#FAIL:}"
            echo -e "  Vector $i: ${RED}FAIL${NC} ($msg)"
            FAILED=$((FAILED + 1))
        fi
    else
        echo -e "  Vector $i: ${YELLOW}UNKNOWN${NC}"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "=========================================="
echo "Summary: $SUCCESS successful, $FAILED failed"
echo "=========================================="

trace_ext="vcd"
[ "$SIM_TYPE" = "cellift" ] && trace_ext="fst"
ls -lh "$TRACE_DIR"/*.$trace_ext 2>/dev/null | head -20
