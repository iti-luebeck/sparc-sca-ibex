#!/bin/bash
#
# WAL++ Hamming Distance/Weight Analysis Script (ALL SIGNALS, Ibex AES-128 Masked)
#
# Generates HD and HW CSV files for all VCD traces using ALL signals.
# Uses --fast-hd-all and --fast-hw-all instead of specific signal lists.
# Supports parallel execution for faster processing.
#
# Usage:
#   ./run_walpp_analysis_all.sh                           # Process all VCDs with defaults
#   ./run_walpp_analysis_all.sh --jobs 8                  # Run 8 parallel jobs
#   ./run_walpp_analysis_all.sh --hd-only                 # Only Hamming Distance
#   ./run_walpp_analysis_all.sh --hw-only                 # Only Hamming Weight
#   ./run_walpp_analysis_all.sh --input /path/to/vcds     # Custom input directory
#   ./run_walpp_analysis_all.sh --output /path/to/csvs    # Custom output directory

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# =============================================================================
# Configuration - Adjust these paths as needed
# =============================================================================

# WAL++ executable
WALPP_BIN="/home/andrija/projects/walpp/build/wal"

# Plot script location (default: plot_trace.py in same directory as this script)
PLOT_SCRIPT="/mnt/nvme1n1p1/cellift-designs/cellift-chipyard/cellift-rocket/sw/scenario_aes128_multi/plot_trace.py"

# Default input directory (VCD files)
INPUT_DIR="/home/andrija/rackstation_home/CellIFT_traces/ibex_masked_aes/vcds"

# Default output directory (CSV files)
OUTPUT_DIR="/home/andrija/rackstation_home/CellIFT_traces/ibex_masked_aes/walpp_all"

# Default plot output directory
PLOT_DIR="/home/andrija/rackstation_home/CellIFT_traces/ibex_masked_aes/walpp_all/plot"

# Default number of parallel jobs (auto-detect CPU cores)
MAX_JOBS=$(nproc 2>/dev/null || echo 4)

# What to compute
COMPUTE_HD=true
COMPUTE_HW=true

# Plotting options
GENERATE_PLOTS=false
PLOT_ONLY=false

# =============================================================================
# Colors for output
# =============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# =============================================================================
# Temporary directory for job status
# =============================================================================
STATUS_DIR=$(mktemp -d)
trap "rm -rf $STATUS_DIR" EXIT

# =============================================================================
# Help function
# =============================================================================
show_help() {
    echo "WAL++ Hamming Distance/Weight Analysis Script (ALL SIGNALS, Ibex AES-128 Masked)"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "This script uses --fast-hd-all and --fast-hw-all to compute"
    echo "Hamming Distance/Weight across ALL signals in the VCD files."
    echo ""
    echo "Analysis Options:"
    echo "  -j, --jobs N          Number of parallel jobs (default: $MAX_JOBS)"
    echo "  -i, --input DIR       Input directory with VCD files (default: vcds/)"
    echo "  -o, --output DIR      Output directory for CSV files (default: walpp_all/)"
    echo "  --hd-only             Compute only Hamming Distance"
    echo "  --hw-only             Compute only Hamming Weight"
    echo "  --walpp PATH          Path to WAL++ executable"
    echo ""
    echo "Plotting Options:"
    echo "  --plot                Generate plots after analysis"
    echo "  --plot-dir DIR        Output directory for plots (default: same as CSV output)"
    echo "  --plot-only           Only generate plots (skip WAL++ analysis)"
    echo "  --plot-script PATH    Path to plot_trace.py script"
    echo ""
    echo "General Options:"
    echo "  -h, --help            Show this help"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Process all with defaults"
    echo "  $0 --jobs 8                           # Use 8 parallel workers"
    echo "  $0 --hd-only --jobs 4                 # HD only, 4 workers"
    echo "  $0 --plot                             # Analyze and generate plots"
    echo "  $0 --plot --plot-dir ./plots          # Plots to custom directory"
    echo "  $0 --plot-only                        # Only generate plots from existing CSVs"
    echo "  $0 --input /path/to/vcds --output /path/to/csvs"
    echo ""
}

# =============================================================================
# Parse command line arguments
# =============================================================================
while [[ $# -gt 0 ]]; do
    case $1 in
        -j|--jobs)
            MAX_JOBS=$2
            shift 2
            ;;
        -i|--input)
            INPUT_DIR=$2
            shift 2
            ;;
        -o|--output)
            OUTPUT_DIR=$2
            shift 2
            ;;
        --hd-only)
            COMPUTE_HD=true
            COMPUTE_HW=false
            shift
            ;;
        --hw-only)
            COMPUTE_HD=false
            COMPUTE_HW=true
            shift
            ;;
        --walpp)
            WALPP_BIN=$2
            shift 2
            ;;
        --plot)
            GENERATE_PLOTS=true
            shift
            ;;
        --plot-dir)
            PLOT_DIR=$2
            GENERATE_PLOTS=true
            shift 2
            ;;
        --plot-only)
            PLOT_ONLY=true
            GENERATE_PLOTS=true
            shift
            ;;
        --plot-script)
            PLOT_SCRIPT=$2
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Set default plot directory if not specified
if [ -z "$PLOT_DIR" ]; then
    PLOT_DIR="$OUTPUT_DIR/plots"
fi

# =============================================================================
# Validation
# =============================================================================
echo "=========================================="
echo "WAL++ Hamming Analysis (ALL SIGNALS)"
echo "=========================================="

# Check plot script if plotting is enabled
if [ "$GENERATE_PLOTS" = true ]; then
    if [ ! -f "$PLOT_SCRIPT" ]; then
        echo -e "${RED}ERROR: Plot script not found: $PLOT_SCRIPT${NC}"
        exit 1
    fi
    echo -e "Plot script: ${GREEN}$PLOT_SCRIPT${NC}"
fi

# Skip WAL++ checks if only plotting
if [ "$PLOT_ONLY" = false ]; then
    # Check WAL++ executable
    if [ ! -x "$WALPP_BIN" ]; then
        echo -e "${RED}ERROR: WAL++ executable not found or not executable: $WALPP_BIN${NC}"
        exit 1
    fi
    echo -e "WAL++ binary: ${GREEN}$WALPP_BIN${NC}"

    # Check input directory
    if [ ! -d "$INPUT_DIR" ]; then
        echo -e "${RED}ERROR: Input directory not found: $INPUT_DIR${NC}"
        exit 1
    fi

    # Count VCD files
    VCD_FILES=("$INPUT_DIR"/*.vcd)
    if [ ! -f "${VCD_FILES[0]}" ]; then
        echo -e "${RED}ERROR: No VCD files found in $INPUT_DIR${NC}"
        exit 1
    fi
    VCD_COUNT=${#VCD_FILES[@]}
    echo -e "Input directory: ${GREEN}$INPUT_DIR${NC} ($VCD_COUNT VCD files)"
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"
echo -e "Output directory: ${GREEN}$OUTPUT_DIR${NC}"

# Create plot directory if plotting
if [ "$GENERATE_PLOTS" = true ]; then
    mkdir -p "$PLOT_DIR"
    echo -e "Plot directory: ${GREEN}$PLOT_DIR${NC}"
fi

# Show configuration
echo ""
echo "Configuration:"
echo "  Parallel jobs: $MAX_JOBS"
if [ "$PLOT_ONLY" = false ]; then
    echo "  Compute HD: $COMPUTE_HD"
    echo "  Compute HW: $COMPUTE_HW"
    echo "  Mode: ALL signals (--fast-hd-all / --fast-hw-all)"
fi
echo "  Generate plots: $GENERATE_PLOTS"
if [ "$PLOT_ONLY" = true ]; then
    echo "  Mode: Plot only (skip analysis)"
fi
echo ""

# =============================================================================
# Worker function - processes a single VCD file
# =============================================================================
process_vcd() {
    local vcd_file=$1
    local basename=$(basename "$vcd_file" .vcd)
    local status_file="$STATUS_DIR/status_${basename}"
    local result=""
    local success=true
    
    # Hamming Distance (all signals)
    if [ "$COMPUTE_HD" = true ]; then
        local hd_output="$OUTPUT_DIR/${basename}_hd.csv"
        if "$WALPP_BIN" --fast-hd-all "$vcd_file" -o "$hd_output" > /dev/null 2>&1; then
            if [ -f "$hd_output" ]; then
                local hd_size=$(du -h "$hd_output" | cut -f1)
                result="${result}HD:$hd_size "
            else
                result="${result}HD:FAIL "
                success=false
            fi
        else
            result="${result}HD:ERROR "
            success=false
        fi
    fi
    
    # Hamming Weight (all signals)
    if [ "$COMPUTE_HW" = true ]; then
        local hw_output="$OUTPUT_DIR/${basename}_hw.csv"
        if "$WALPP_BIN" --fast-hw-all "$vcd_file" -o "$hw_output" > /dev/null 2>&1; then
            if [ -f "$hw_output" ]; then
                local hw_size=$(du -h "$hw_output" | cut -f1)
                result="${result}HW:$hw_size"
            else
                result="${result}HW:FAIL"
                success=false
            fi
        else
            result="${result}HW:ERROR"
            success=false
        fi
    fi
    
    if [ "$success" = true ]; then
        echo "OK:$result" > "$status_file"
    else
        echo "FAIL:$result" > "$status_file"
    fi
}

# Export function and variables for subshells
export -f process_vcd
export WALPP_BIN OUTPUT_DIR STATUS_DIR COMPUTE_HD COMPUTE_HW

# =============================================================================
# Main processing loop with parallelization (skip if --plot-only)
# =============================================================================
if [ "$PLOT_ONLY" = false ]; then

echo "Processing $VCD_COUNT VCD files with $MAX_JOBS parallel jobs..."
echo ""

START_TIME=$(date +%s)
COMPLETED=0

# Launch jobs
RUNNING=0
declare -a PIDS
declare -a BASENAMES

for vcd_file in "${VCD_FILES[@]}"; do
    basename=$(basename "$vcd_file" .vcd)
    
    # Start job in background
    process_vcd "$vcd_file" &
    PIDS+=($!)
    BASENAMES+=("$basename")
    RUNNING=$((RUNNING + 1))
    
    # Throttle if we hit max jobs
    if [ $RUNNING -ge $MAX_JOBS ]; then
        # Wait for any job to finish
        wait -n 2>/dev/null || wait ${PIDS[0]}
        RUNNING=$((RUNNING - 1))
        COMPLETED=$((COMPLETED + 1))
        PERCENT=$((COMPLETED * 100 / VCD_COUNT))
        ELAPSED=$(($(date +%s) - START_TIME))
        if [ $COMPLETED -gt 0 ] && [ $ELAPSED -gt 0 ]; then
            RATE=$(echo "scale=2; $COMPLETED / $ELAPSED" | bc 2>/dev/null || echo "0")
            REMAINING=$((VCD_COUNT - COMPLETED))
            ETA=$((REMAINING / $(echo "$RATE" | cut -d'.' -f1) + 1))
            printf "\rProgress: %d/%d (%d%%) | Elapsed: %ds | ETA: %ds | Running: %d jobs" $COMPLETED $VCD_COUNT $PERCENT $ELAPSED $ETA $RUNNING
        else
            printf "\rProgress: %d/%d (%d%%) | Elapsed: %ds | Running: %d jobs" $COMPLETED $VCD_COUNT $PERCENT $ELAPSED $RUNNING
        fi
    fi
done

# Wait for all remaining jobs
while [ $COMPLETED -lt $VCD_COUNT ]; do
    wait -n 2>/dev/null && {
        COMPLETED=$((COMPLETED + 1))
        PERCENT=$((COMPLETED * 100 / VCD_COUNT))
        ELAPSED=$(($(date +%s) - START_TIME))
        if [ $COMPLETED -lt $VCD_COUNT ] && [ $ELAPSED -gt 0 ]; then
            RATE=$(echo "scale=2; $COMPLETED / $ELAPSED" | bc 2>/dev/null || echo "1")
            REMAINING=$((VCD_COUNT - COMPLETED))
            ETA=$((REMAINING / $(echo "$RATE" | cut -d'.' -f1) + 1))
            printf "\rProgress: %d/%d (%d%%) | Elapsed: %ds | ETA: %ds" $COMPLETED $VCD_COUNT $PERCENT $ELAPSED $ETA
        else
            printf "\rProgress: %d/%d (100%%) | Elapsed: %ds" $COMPLETED $VCD_COUNT $ELAPSED
        fi
    }
done
echo ""

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

# =============================================================================
# Collect and display results
# =============================================================================
echo "Results:"
echo "--------"

SUCCESS=0
FAILED=0

for basename in "${BASENAMES[@]}"; do
    status_file="$STATUS_DIR/status_${basename}"
    if [ -f "$status_file" ]; then
        status=$(cat "$status_file")
        if [[ "$status" == OK:* ]]; then
            details="${status#OK:}"
            echo -e "  $basename: ${GREEN}OK${NC} ($details)"
            SUCCESS=$((SUCCESS + 1))
        else
            details="${status#FAIL:}"
            echo -e "  $basename: ${RED}FAIL${NC} ($details)"
            FAILED=$((FAILED + 1))
        fi
    else
        echo -e "  $basename: ${YELLOW}UNKNOWN${NC}"
        FAILED=$((FAILED + 1))
    fi
done

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="
echo "  Total VCDs: $VCD_COUNT"
echo "  Successful: $SUCCESS"
echo "  Failed: $FAILED"
echo "  Time: ${ELAPSED}s"
echo ""

# Show output files
echo "Output files:"
if [ "$COMPUTE_HD" = true ]; then
    HD_COUNT=$(ls -1 "$OUTPUT_DIR"/*_hd.csv 2>/dev/null | wc -l)
    echo "  HD CSVs: $HD_COUNT files"
fi
if [ "$COMPUTE_HW" = true ]; then
    HW_COUNT=$(ls -1 "$OUTPUT_DIR"/*_hw.csv 2>/dev/null | wc -l)
    echo "  HW CSVs: $HW_COUNT files"
fi
echo ""
echo "Output directory: $OUTPUT_DIR"
ls -lh "$OUTPUT_DIR"/*.csv 2>/dev/null | head -20

fi  # End of PLOT_ONLY check for WAL++ analysis

# =============================================================================
# Plot generation (if requested)
# =============================================================================
if [ "$GENERATE_PLOTS" = true ]; then
    echo ""
    echo "=========================================="
    echo "Generating Plots"
    echo "=========================================="
    
    # Check if plot script exists
    if [ ! -f "$PLOT_SCRIPT" ]; then
        echo -e "${RED}Error: Plot script not found: $PLOT_SCRIPT${NC}"
        echo "Please specify a valid plot script with --plot-script"
        exit 1
    fi
    
    # Create plot directory
    mkdir -p "$PLOT_DIR"
    
    # Find all CSV files to plot
    HD_CSVS=()
    HW_CSVS=()
    
    if [ "$COMPUTE_HD" = true ] || [ "$PLOT_ONLY" = true ]; then
        while IFS= read -r -d '' file; do
            HD_CSVS+=("$file")
        done < <(find "$OUTPUT_DIR" -name "*_hd.csv" -print0 2>/dev/null | sort -z)
    fi
    
    if [ "$COMPUTE_HW" = true ] || [ "$PLOT_ONLY" = true ]; then
        while IFS= read -r -d '' file; do
            HW_CSVS+=("$file")
        done < <(find "$OUTPUT_DIR" -name "*_hw.csv" -print0 2>/dev/null | sort -z)
    fi
    
    TOTAL_PLOTS=$((${#HD_CSVS[@]} + ${#HW_CSVS[@]}))
    
    if [ $TOTAL_PLOTS -eq 0 ]; then
        echo -e "${YELLOW}Warning: No CSV files found to plot${NC}"
    else
        echo "Found $TOTAL_PLOTS CSV files to plot"
        echo "  HD files: ${#HD_CSVS[@]}"
        echo "  HW files: ${#HW_CSVS[@]}"
        echo "  Output directory: $PLOT_DIR"
        echo ""
        
        # Worker function for plotting
        plot_csv() {
            local csv_file=$1
            local plot_dir=$2
            local plot_script=$3
            local basename=$(basename "$csv_file" .csv)
            local output_plot="$plot_dir/${basename}.png"
            
            if python3 "$plot_script" "$csv_file" -o "$output_plot" > /dev/null 2>&1; then
                if [ -f "$output_plot" ]; then
                    echo "OK"
                else
                    echo "FAIL"
                fi
            else
                echo "ERROR"
            fi
        }
        export -f plot_csv
        
        PLOT_START=$(date +%s)
        PLOT_SUCCESS=0
        PLOT_FAILED=0
        
        echo "Plotting with $MAX_JOBS parallel jobs..."
        
        # Process all CSV files
        ALL_CSVS=("${HD_CSVS[@]}" "${HW_CSVS[@]}")
        RUNNING=0
        declare -a PLOT_PIDS
        declare -a PLOT_FILES
        declare -a PLOT_RESULTS
        
        for csv_file in "${ALL_CSVS[@]}"; do
            basename=$(basename "$csv_file" .csv)
            output_plot="$PLOT_DIR/${basename}.png"
            
            # Start job in background, capture result in temp file
            (
                result=$(plot_csv "$csv_file" "$PLOT_DIR" "$PLOT_SCRIPT")
                echo "$result" > "$STATUS_DIR/plot_${basename}"
            ) &
            PLOT_PIDS+=($!)
            PLOT_FILES+=("$csv_file")
            RUNNING=$((RUNNING + 1))
            
            # Throttle if we hit max jobs
            if [ $RUNNING -ge $MAX_JOBS ]; then
                wait -n 2>/dev/null || wait ${PLOT_PIDS[0]}
                RUNNING=$((RUNNING - 1))
            fi
        done
        
        # Wait for all remaining jobs
        wait
        
        PLOT_END=$(date +%s)
        PLOT_ELAPSED=$((PLOT_END - PLOT_START))
        
        # Collect results
        echo ""
        echo "Plot Results:"
        echo "-------------"
        for csv_file in "${PLOT_FILES[@]}"; do
            basename=$(basename "$csv_file" .csv)
            status_file="$STATUS_DIR/plot_${basename}"
            if [ -f "$status_file" ]; then
                result=$(cat "$status_file")
                if [ "$result" = "OK" ]; then
                    echo -e "  $basename.png: ${GREEN}OK${NC}"
                    PLOT_SUCCESS=$((PLOT_SUCCESS + 1))
                else
                    echo -e "  $basename.png: ${RED}$result${NC}"
                    PLOT_FAILED=$((PLOT_FAILED + 1))
                fi
            else
                echo -e "  $basename.png: ${YELLOW}UNKNOWN${NC}"
                PLOT_FAILED=$((PLOT_FAILED + 1))
            fi
        done
        
        echo ""
        echo "Plot Summary:"
        echo "  Total plots: $TOTAL_PLOTS"
        echo "  Successful: $PLOT_SUCCESS"
        echo "  Failed: $PLOT_FAILED"
        echo "  Time: ${PLOT_ELAPSED}s"
        echo ""
        echo "Plot directory: $PLOT_DIR"
        ls -lh "$PLOT_DIR"/*.png 2>/dev/null | head -20
        
        if [ $PLOT_FAILED -gt 0 ]; then
            exit 1
        fi
    fi
fi

# Final cleanup
rm -rf "$STATUS_DIR"

# Exit with error if WAL++ analysis had failures (only relevant if not plot-only mode)
if [ "$PLOT_ONLY" = false ] && [ ${FAILED:-0} -gt 0 ]; then
    exit 1
fi

echo ""
echo "Done!"
