#!/usr/bin/env python3
"""
Correlation Power Analysis (CPA) Attack on 3x3 Matrix-Vector Multiplication

This script attempts to recover the weight matrix from side-channel
traces (Hamming Distance/Weight) collected during matrix-vector multiplication.

Attack Model:
- Known: Input vectors (from header files), network structure (3x3 matrix)
- Unknown: Weights (uint8_t, 0-255 range) - we try to recover these
- Power Models:
  * HW (Hamming Weight): Power ~ number of 1-bits in intermediate value
  * HD (Hamming Distance): Power ~ bit flips from previous to current value

The attacker knows:
  - Operation: output = weights * input (3x3 @ 3x1)
  - Data types: uint8_t weights, uint8_t inputs, uint16_t outputs
  - Matrix dimensions: 3x3
  - Row computations happen sequentially (different timing windows)

The attack correlates hypothetical power consumption (based on guessed weights)
with actual measured power traces. Uses time-windowed analysis to distinguish
weight rows based on computation timing.

Usage:
    python3 cpa_attack.py --traces-dir ./traces/walpp_all \
                          --inputs-dir . \
                          --output-dir ./cpa_results

    python3 cpa_attack.py --traces-dir ./traces/walpp_all \
                          --inputs-dir . \
                          --output-dir ./cpa_results \
                          --num-traces 100 \
                          --weight-range 0 255
"""

import argparse
import os
import sys
import re
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
import json
from datetime import datetime


# Matrix dimensions (must match tinyai.c)
SIZE = 3  # 3x3 weight matrix, 3-element input/output vectors

# Data types (attacker knowledge)
# - Weights: uint8_t (0-255)
# - Inputs: uint8_t (0-255)  
# - Outputs: uint16_t (0-65535, to hold accumulation)


@dataclass
class AttackConfig:
    """Configuration for the CPA attack."""
    traces_dir: Path
    inputs_dir: Path
    output_dir: Path
    num_traces: int
    weight_min: int
    weight_max: int
    weight_step: int
    trace_type: str  # 'hd' or 'hw'
    trace_prefix: str  # 'vanilla' or 'cellift'
    hypothesis_model: str  # 'hw', 'hd', or 'both'
    verbose: bool


@dataclass
class AttackResult:
    """Result of attacking a single weight."""
    layer: str
    neuron_idx: int
    input_idx: int
    best_guess: int
    correlation: float
    all_correlations: np.ndarray
    weight_candidates: np.ndarray


def hamming_weight(value: int) -> int:
    """Compute Hamming Weight (number of 1 bits) of an integer."""
    # For uint8_t * uint8_t, result fits in 16 bits
    value = value & 0xFFFF
    return bin(value).count('1')


def hamming_weight_vectorized(values: np.ndarray) -> np.ndarray:
    """Vectorized Hamming Weight computation for uint16 values."""
    values = values.astype(np.uint32) & 0xFFFF
    
    # Count bits using bit manipulation
    hw = np.zeros(values.shape, dtype=np.int32)
    for i in range(16):
        hw += (values >> i) & 1
    return hw


def parse_input_header(header_path: Path) -> np.ndarray:
    """
    Parse an input header file and extract the test input vector.
    
    Expected format:
        static const uint8_t test_input[SIZE] = { v0, v1, v2 };
    
    Returns:
        numpy array of shape (SIZE,) with uint8 values
    """
    with open(header_path, 'r') as f:
        content = f.read()
    
    # Find the test_input array
    pattern = r'test_input\[.*?\]\s*=\s*\{([^}]+)\}'
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        raise ValueError(f"Could not parse input from {header_path}")
    
    array_content = match.group(1)
    
    # Parse comma-separated values
    values = []
    for v in array_content.split(','):
        v = v.strip()
        # Remove comments
        if '/*' in v:
            v = v[:v.index('/*')].strip()
        if v and v.isdigit():
            values.append(int(v))
    
    if len(values) != SIZE:
        raise ValueError(f"Expected {SIZE} values, got {len(values)} in {header_path}")
    
    return np.array(values, dtype=np.uint8)


def load_trace(csv_path: Path) -> np.ndarray:
    """
    Load a WAL++ trace CSV file.
    
    Returns:
        numpy array of shape (num_cycles,) with HD or HW values
    """
    try:
        # Try loading with numpy
        data = np.loadtxt(csv_path, delimiter=',', skiprows=1)
        if data.ndim == 1:
            return data
        else:
            # Assume second column is the value
            return data[:, 1] if data.shape[1] > 1 else data[:, 0]
    except Exception as e:
        print(f"Error loading {csv_path}: {e}")
        # Try manual parsing
        values = []
        with open(csv_path, 'r') as f:
            next(f)  # Skip header
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 2:
                    try:
                        values.append(float(parts[1]))
                    except ValueError:
                        continue
        return np.array(values)


def collect_traces_and_inputs(config: AttackConfig) -> Tuple[np.ndarray, np.ndarray]:
    """
    Collect all traces and corresponding inputs.
    
    Returns:
        traces: numpy array of shape (num_traces, trace_length)
        inputs: numpy array of shape (num_traces, SIZE)
    """
    traces_list = []
    inputs_list = []
    
    # Find all trace files - use the specified prefix (vanilla or cellift)
    trace_pattern = f"{config.trace_prefix}_*_{config.trace_type}.csv"
    trace_files = sorted(config.traces_dir.glob(trace_pattern))
    
    if not trace_files:
        raise FileNotFoundError(f"No {config.trace_prefix}_{config.trace_type.upper()} trace files found in {config.traces_dir}")
    
    # Limit to requested number of traces
    trace_files = trace_files[:config.num_traces]
    
    print(f"Found {len(trace_files)} {config.trace_prefix} trace files")
    
    for trace_file in trace_files:
        # Extract trace index from filename (e.g., vanilla_0_hd.csv -> 0)
        basename = trace_file.stem.replace(f"_{config.trace_type}", "")
        match = re.search(r'(\d+)$', basename)
        if not match:
            print(f"Warning: Could not extract index from {trace_file.name}, skipping")
            continue
        
        trace_idx = int(match.group(1))
        
        # Find corresponding input header
        input_header = config.inputs_dir / f"input_{trace_idx}.h"
        if not input_header.exists():
            print(f"Warning: Input header not found for trace {trace_idx}: {input_header}")
            continue
        
        # Load trace
        trace = load_trace(trace_file)
        if len(trace) == 0:
            print(f"Warning: Empty trace in {trace_file.name}")
            continue
        
        # Parse input vector
        try:
            input_vec = parse_input_header(input_header)
        except Exception as e:
            print(f"Warning: Could not parse {input_header}: {e}")
            continue
        
        traces_list.append(trace)
        inputs_list.append(input_vec)
        
        if config.verbose:
            print(f"  Loaded trace {trace_idx}: {len(trace)} samples, input: {input_vec}")
    
    if not traces_list:
        raise ValueError("No valid trace-input pairs found")
    
    # Align trace lengths (pad or truncate to minimum length)
    min_len = min(len(t) for t in traces_list)
    traces_array = np.array([t[:min_len] for t in traces_list])
    inputs_array = np.array(inputs_list)
    
    print(f"Collected {len(traces_list)} trace-input pairs")
    print(f"Trace matrix shape: {traces_array.shape}")
    print(f"Input matrix shape: {inputs_array.shape}")
    
    return traces_array, inputs_array


def pearson_correlation(x: np.ndarray, y: np.ndarray) -> float:
    """Compute Pearson correlation coefficient between two arrays."""
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    
    x_mean = np.mean(x)
    y_mean = np.mean(y)
    
    numerator = np.sum((x - x_mean) * (y - y_mean))
    denominator = np.sqrt(np.sum((x - x_mean)**2) * np.sum((y - y_mean)**2))
    
    if denominator == 0:
        return 0.0
    
    return numerator / denominator


def attack_weight_input_hidden(
    traces: np.ndarray,
    inputs: np.ndarray,
    row_idx: int,
    col_idx: int,
    config: AttackConfig
) -> AttackResult:
    """
    Attack a single weight in the 3x3 matrix.
    
    For weight w[row_idx][col_idx]:
    - Compute hypothetical intermediate: h = w_guess * input[col_idx]
    - Compute Hamming Weight of h
    - Correlate with trace across all traces
    
    The attacker's hypothesis:
      For each weight guess w_guess (0-255), the intermediate value
      during computation is: intermediate = w_guess * input[col_idx]
      
      The power consumption is modeled as proportional to HW(intermediate)
    
    Args:
        traces: Shape (num_traces, trace_length)
        inputs: Shape (num_traces, SIZE)
        row_idx: Row index in weight matrix (0 to SIZE-1)
        col_idx: Column index / input index (0 to SIZE-1)
        config: Attack configuration
    
    Returns:
        AttackResult with best guess and correlation
    """
    num_traces = traces.shape[0]
    
    # Weight candidates to try (uint8_t: 0-255)
    weight_candidates = np.arange(
        config.weight_min, 
        config.weight_max + 1, 
        config.weight_step,
        dtype=np.uint8
    )
    
    correlations = np.zeros(len(weight_candidates))
    
    for w_idx, w_guess in enumerate(weight_candidates):
        # Compute hypothetical power for each trace
        hypothetical_power = []
        
        for t_idx in range(num_traces):
            # Get input value for this column
            input_val = inputs[t_idx, col_idx]
            
            # Compute intermediate value (uint8 * uint8 -> uint16)
            intermediate = int(w_guess) * int(input_val)
            
            # Compute Hamming Weight as power model
            hw = hamming_weight(intermediate)
            hypothetical_power.append(hw)
        
        hypothetical_power = np.array(hypothetical_power)
        
        # For measured power, use mean of trace as aggregate power
        measured_power = np.mean(traces, axis=1)
        
        # Compute correlation
        correlations[w_idx] = abs(pearson_correlation(hypothetical_power, measured_power))
    
    # Find best guess
    best_idx = np.argmax(correlations)
    best_guess = weight_candidates[best_idx]
    best_corr = correlations[best_idx]
    
    return AttackResult(
        layer='weights',
        neuron_idx=row_idx,
        input_idx=col_idx,
        best_guess=int(best_guess),
        correlation=float(best_corr),
        all_correlations=correlations,
        weight_candidates=weight_candidates
    )


def attack_weight_time_windowed(
    traces: np.ndarray,
    inputs: np.ndarray,
    row_idx: int,
    col_idx: int,
    config: AttackConfig,
) -> AttackResult:
    """
    Attack a weight using row-specific time windows.
    
    Based on analysis, row computations happen at different times in the trace:
      - Row 0: approximately t=100-250
      - Row 1: approximately t=250-400
      - Row 2: approximately t=400-550
    
    By restricting the search to the correct time window for each row,
    we can distinguish weights in different rows that multiply the same input.
    
    Note: HW equivalence still applies - weights differing by power of 2
    will have identical HW patterns: HW(w*x) = HW(2w*x) for all x.
    
    Hypothesis: Power ~ HW(w_guess * input[col_idx])
    """
    num_traces = traces.shape[0]
    trace_len = traces.shape[1]
    
    # Row-specific time windows (empirically determined from trace analysis)
    # These windows correspond to when each row's computation appears in the trace
    row_windows = [
        (100, 250),   # Row 0 computation window
        (250, 400),   # Row 1 computation window
        (400, 550),   # Row 2 computation window
    ]
    
    # Get the time window for this row (clamp to SIZE-1 for safety)
    window_idx = min(row_idx, len(row_windows) - 1)
    poi_start, poi_end = row_windows[window_idx]
    poi_end = min(poi_end, trace_len)
    
    # Weight candidates (uint8_t range)
    weight_candidates = np.arange(
        config.weight_min,
        config.weight_max + 1,
        config.weight_step,
        dtype=np.uint16  # Use uint16 to avoid overflow issues
    )
    
    best_correlations = np.zeros(len(weight_candidates))
    best_time_points = np.zeros(len(weight_candidates), dtype=np.int32)
    
    # Compute hypothetical power for all guesses
    for w_idx, w_guess in enumerate(weight_candidates):
        hypothetical_power = np.zeros(num_traces)
        
        for t_idx in range(num_traces):
            input_val = int(inputs[t_idx, col_idx])
            intermediate = int(w_guess) * input_val
            hypothetical_power[t_idx] = hamming_weight(intermediate)
        
        # Skip if hypothesis has no variance (e.g., w=0)
        if np.std(hypothetical_power) < 1e-10:
            best_correlations[w_idx] = 0.0
            continue
        
        # Search within the row-specific time window
        best_point_corr = 0.0
        best_point_t = poi_start
        
        for t in range(poi_start, poi_end):
            measured = traces[:, t]
            
            if np.std(measured) < 1e-10:
                continue
                
            corr = abs(pearson_correlation(hypothetical_power, measured))
            if corr > best_point_corr:
                best_point_corr = corr
                best_point_t = t
        
        best_correlations[w_idx] = best_point_corr
        best_time_points[w_idx] = best_point_t
    
    best_idx = np.argmax(best_correlations)
    
    return AttackResult(
        layer='weights',
        neuron_idx=row_idx,
        input_idx=col_idx,
        best_guess=int(weight_candidates[best_idx]),
        correlation=float(best_correlations[best_idx]),
        all_correlations=best_correlations,
        weight_candidates=weight_candidates
    )


def attack_weight_full_trace(
    traces: np.ndarray,
    inputs: np.ndarray,
    row_idx: int,
    col_idx: int,
    config: AttackConfig,
) -> AttackResult:
    """
    Attack a weight by searching ALL time points (no windowing).
    
    This is a fallback when we don't know the timing precisely.
    The downside is that weights in the same column may correlate
    at the same time points (since they multiply the same input).
    """
    num_traces = traces.shape[0]
    trace_len = traces.shape[1]
    
    # Weight candidates (uint8_t range)
    weight_candidates = np.arange(
        config.weight_min,
        config.weight_max + 1,
        config.weight_step,
        dtype=np.uint16
    )
    
    best_correlations = np.zeros(len(weight_candidates))
    
    for w_idx, w_guess in enumerate(weight_candidates):
        hypothetical_power = np.zeros(num_traces)
        
        for t_idx in range(num_traces):
            input_val = int(inputs[t_idx, col_idx])
            intermediate = int(w_guess) * input_val
            hypothetical_power[t_idx] = hamming_weight(intermediate)
        
        # Search all time points
        best_point_corr = 0.0
        for t in range(trace_len):
            measured = traces[:, t]
            if np.std(measured) < 1e-10:
                continue
            corr = abs(pearson_correlation(hypothetical_power, measured))
            if corr > best_point_corr:
                best_point_corr = corr
        
        best_correlations[w_idx] = best_point_corr
    
    best_idx = np.argmax(best_correlations)
    
    return AttackResult(
        layer='weights',
        neuron_idx=row_idx,
        input_idx=col_idx,
        best_guess=int(weight_candidates[best_idx]),
        correlation=float(best_correlations[best_idx]),
        all_correlations=best_correlations,
        weight_candidates=weight_candidates
    )


def run_full_attack(
    traces: np.ndarray,
    inputs: np.ndarray,
    config: AttackConfig
) -> Dict[str, AttackResult]:
    """
    Run CPA attack on all weights in the 3x3 matrix.
    
    Uses time-windowed analysis to distinguish weights in different rows
    that multiply the same input element.
    """
    results = {}
    
    trace_len = traces.shape[1]
    cycles_per_mult = trace_len // (SIZE * SIZE + 1)
    
    print(f"\nAttacking 3x3 weight matrix ({SIZE}x{SIZE} = {SIZE*SIZE} weights)")
    print(f"Trace length: {trace_len} samples, ~{cycles_per_mult} cycles per multiplication")
    print(f"Hypothesis model: {config.hypothesis_model.upper()}")
    print("=" * 60)
    
    for row_idx in range(SIZE):
        for col_idx in range(SIZE):
            key = f"w_{row_idx}_{col_idx}"
            mult_idx = row_idx * SIZE + col_idx
            
            if config.verbose:
                print(f"Attacking weight [{row_idx}][{col_idx}] (mult #{mult_idx})...", end=" ")
            
            # Use time-windowed attack
            result = attack_weight_time_windowed(
                traces, inputs, row_idx, col_idx, config
            )
            
            results[key] = result
            
            if config.verbose:
                print(f"Best guess: {result.best_guess:3d}, Correlation: {result.correlation:.4f}")
    
    return results


def plot_correlation_results(
    result: AttackResult,
    output_path: Path,
    true_weight: Optional[int] = None
):
    """Plot correlation vs weight guess for a single weight."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.plot(result.weight_candidates, result.all_correlations, 'b-', linewidth=0.5)
    ax.axvline(x=result.best_guess, color='r', linestyle='--', 
               label=f'Best guess: {result.best_guess}')
    
    if true_weight is not None:
        ax.axvline(x=true_weight, color='g', linestyle='-',
                   label=f'True weight: {true_weight}')
    
    ax.set_xlabel('Weight Guess')
    ax.set_ylabel('Correlation')
    ax.set_title(f'CPA Attack: {result.layer} [{result.neuron_idx}][{result.input_idx}]\n'
                 f'Best correlation: {result.correlation:.4f}')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_summary_heatmap(
    results: Dict[str, AttackResult],
    output_path: Path
):
    """Plot a heatmap of correlation values for all weights."""
    # Create correlation matrix
    corr_matrix = np.zeros((SIZE, SIZE))
    guess_matrix = np.zeros((SIZE, SIZE))
    
    for row_idx in range(SIZE):
        for col_idx in range(SIZE):
            key = f"w_{row_idx}_{col_idx}"
            if key in results:
                corr_matrix[row_idx, col_idx] = results[key].correlation
                guess_matrix[row_idx, col_idx] = results[key].best_guess
    
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # Correlation heatmap
    im1 = axes[0].imshow(corr_matrix, cmap='hot', aspect='auto')
    axes[0].set_xlabel('Column (Input Index)')
    axes[0].set_ylabel('Row (Output Index)')
    axes[0].set_title('Correlation Coefficients')
    axes[0].set_xticks(range(SIZE))
    axes[0].set_yticks(range(SIZE))
    plt.colorbar(im1, ax=axes[0])
    
    # Add correlation values as text
    for i in range(SIZE):
        for j in range(SIZE):
            axes[0].text(j, i, f'{corr_matrix[i,j]:.3f}',
                        ha='center', va='center', fontsize=10,
                        color='white' if corr_matrix[i,j] > 0.5 else 'black')
    
    # Weight guess heatmap
    im2 = axes[1].imshow(guess_matrix, cmap='viridis', aspect='auto',
                         vmin=0, vmax=255)
    axes[1].set_xlabel('Column (Input Index)')
    axes[1].set_ylabel('Row (Output Index)')
    axes[1].set_title('Recovered Weight Guesses (uint8)')
    axes[1].set_xticks(range(SIZE))
    axes[1].set_yticks(range(SIZE))
    plt.colorbar(im2, ax=axes[1], label='Weight (0-255)')
    
    # Add weight values as text
    for i in range(SIZE):
        for j in range(SIZE):
            axes[1].text(j, i, f'{int(guess_matrix[i,j])}',
                        ha='center', va='center', fontsize=12,
                        color='white' if guess_matrix[i,j] < 128 else 'black')
    
    plt.suptitle('CPA Attack Summary - 3x3 Weight Matrix')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def save_results_json(
    results: Dict[str, AttackResult],
    output_path: Path,
    config: AttackConfig
):
    """Save attack results to JSON."""
    output = {
        'timestamp': datetime.now().isoformat(),
        'config': {
            'traces_dir': str(config.traces_dir),
            'inputs_dir': str(config.inputs_dir),
            'num_traces': config.num_traces,
            'weight_range': [config.weight_min, config.weight_max],
            'weight_step': config.weight_step,
            'trace_type': config.trace_type,
        },
        'recovered_weights': {},
        'correlations': {},
    }
    
    for key, result in results.items():
        output['recovered_weights'][key] = result.best_guess
        output['correlations'][key] = result.correlation
    
    # Format as weight matrix
    weight_matrix = []
    for row_idx in range(SIZE):
        row = []
        for col_idx in range(SIZE):
            key = f"w_{row_idx}_{col_idx}"
            row.append(results[key].best_guess if key in results else 0)
        weight_matrix.append(row)
    
    output['recovered_weight_matrix'] = weight_matrix
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description='CPA Attack on TinyAI Neural Network Weights',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic attack with defaults
  python3 cpa_attack.py --traces-dir ./traces/walpp_all --inputs-dir .

  # Specify output directory
  python3 cpa_attack.py --traces-dir ./traces/walpp_all \\
                        --inputs-dir . \\
                        --output-dir ./cpa_results

  # Use HW traces instead of HD
  python3 cpa_attack.py --traces-dir ./traces/walpp_all \\
                        --inputs-dir . \\
                        --trace-type hw

  # Fine-grained weight search (slower but more accurate)
  python3 cpa_attack.py --traces-dir ./traces/walpp_all \\
                        --inputs-dir . \\
                        --weight-range 0 255 --weight-step 1
"""
    )
    
    parser.add_argument(
        '--traces-dir', '-t',
        type=Path,
        required=True,
        help='Directory containing WAL++ trace CSV files'
    )
    
    parser.add_argument(
        '--inputs-dir', '-i',
        type=Path,
        required=True,
        help='Directory containing input header files (input_0.h, input_1.h, ...)'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        type=Path,
        default=Path('./cpa_results'),
        help='Output directory for results and plots (default: ./cpa_results)'
    )
    
    parser.add_argument(
        '--num-traces', '-n',
        type=int,
        default=100,
        help='Maximum number of traces to use (default: 100)'
    )
    
    parser.add_argument(
        '--trace-type',
        choices=['hd', 'hw'],
        default='hw',
        help='Type of trace to use: hd (Hamming Distance) or hw (Hamming Weight)'
    )
    
    parser.add_argument(
        '--trace-prefix',
        choices=['vanilla', 'cellift'],
        default='vanilla',
        help='Trace file prefix: vanilla (untainted) or cellift (tainted)'
    )
    
    parser.add_argument(
        '--hypothesis-model',
        choices=['hw', 'hd', 'both'],
        default='hw',
        help='Hypothesis power model: hw (Hamming Weight), hd (Hamming Distance), both'
    )
    
    parser.add_argument(
        '--weight-range',
        type=int,
        nargs=2,
        default=[0, 255],
        metavar=('MIN', 'MAX'),
        help='Range of weight values to try (default: 0 255 for uint8_t)'
    )
    
    parser.add_argument(
        '--weight-step',
        type=int,
        default=4,
        help='Step size for weight search (default: 4)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    # Create config
    config = AttackConfig(
        traces_dir=args.traces_dir,
        inputs_dir=args.inputs_dir,
        output_dir=args.output_dir,
        num_traces=args.num_traces,
        weight_min=args.weight_range[0],
        weight_max=args.weight_range[1],
        weight_step=args.weight_step,
        trace_type=args.trace_type,
        trace_prefix=args.trace_prefix,
        hypothesis_model=args.hypothesis_model,
        verbose=args.verbose
    )
    
    print("=" * 60)
    print("CPA Attack on 3x3 Matrix-Vector Multiplication")
    print("=" * 60)
    print(f"Traces directory: {config.traces_dir}")
    print(f"Inputs directory: {config.inputs_dir}")
    print(f"Output directory: {config.output_dir}")
    print(f"Trace prefix: {config.trace_prefix}")
    print(f"Trace type: {config.trace_type.upper()}")
    print(f"Hypothesis model: {config.hypothesis_model.upper()}")
    print(f"Weight search range: [{config.weight_min}, {config.weight_max}] step {config.weight_step}")
    print(f"Max traces: {config.num_traces}")
    print()
    print("Attacker's knowledge:")
    print(f"  - Operation: output = weights * input ({SIZE}x{SIZE} @ {SIZE}x1)")
    print(f"  - Data types: uint8_t weights, uint8_t inputs")
    print(f"  - Unknown: weight values (trying to recover)")
    print()
    
    # Create output directory
    config.output_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = config.output_dir / 'plots'
    plots_dir.mkdir(exist_ok=True)
    
    # Load traces and inputs
    print("Loading traces and inputs...")
    try:
        traces, inputs = collect_traces_and_inputs(config)
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    # Run attack
    print("\nRunning CPA attack...")
    results = run_full_attack(traces, inputs, config)
    
    # Save results
    print("\nSaving results...")
    
    # JSON results
    json_path = config.output_dir / 'attack_results.json'
    save_results_json(results, json_path, config)
    print(f"  Results saved to: {json_path}")
    
    # Summary heatmap
    heatmap_path = config.output_dir / 'correlation_heatmap.png'
    plot_summary_heatmap(results, heatmap_path)
    print(f"  Heatmap saved to: {heatmap_path}")
    
    # Individual weight plots (only plot first few to avoid too many files)
    print("  Generating individual weight plots...")
    for row_idx in range(SIZE):
        for col_idx in range(SIZE):
            key = f"w_{row_idx}_{col_idx}"
            if key in results:
                plot_path = plots_dir / f'{key}_correlation.png'
                plot_correlation_results(results[key], plot_path)
    print(f"  Individual plots saved to: {plots_dir}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("Attack Summary")
    print("=" * 60)
    
    print("\nRecovered 3x3 Weight Matrix:")
    print("(Row x Column)")
    print("-" * 40)
    
    for row_idx in range(SIZE):
        row = []
        for col_idx in range(SIZE):
            key = f"w_{row_idx}_{col_idx}"
            if key in results:
                row.append(f"{results[key].best_guess:3d}")
            else:
                row.append("  ?")
        print(f"  Row {row_idx}: [{', '.join(row)}]")
    
    # Correlation statistics
    correlations = [r.correlation for r in results.values()]
    print(f"\nCorrelation Statistics:")
    print(f"  Mean: {np.mean(correlations):.4f}")
    print(f"  Max:  {np.max(correlations):.4f}")
    print(f"  Min:  {np.min(correlations):.4f}")
    
    # Compare with true weights (from main.S)
    # weights:
    #     .byte  10,  20,  30    /* Row 0 */
    #     .byte  40,  50,  60    /* Row 1 */
    #     .byte  70,  80,  90    /* Row 2 */
    true_weights = [
        [10, 20, 30],   # Row 0
        [40, 50, 60],   # Row 1
        [70, 80, 90],   # Row 2
    ]
    
    def get_hw_equivalence_class(w):
        """Get HW equivalence class: weights that produce same HW pattern."""
        # Find base (divide by powers of 2 until odd)
        base = w
        while base > 0 and base % 2 == 0:
            base //= 2
        if base == 0:
            return [0]
        # Class is base * {1, 2, 4, 8, ...} within 0-255
        equiv = []
        mult = base
        while mult <= 255:
            equiv.append(mult)
            mult *= 2
        return equiv
    
    print("\nComparison with True Weights:")
    print("-" * 80)
    print(f"{'Weight':<12} {'Recovered':>10} {'True':>8} {'Error':>8} {'Corr':>8} {'Equiv. Class':<25}")
    print("-" * 80)
    
    correct = 0
    equiv_match = 0
    total = 0
    
    for row_idx in range(SIZE):
        for col_idx in range(SIZE):
            key = f"w_{row_idx}_{col_idx}"
            if key in results:
                recovered = results[key].best_guess
                true_val = true_weights[row_idx][col_idx]
                error = abs(recovered - true_val)
                corr = results[key].correlation
                
                # Check equivalence class
                equiv_class = get_hw_equivalence_class(recovered)
                equiv_str = str(equiv_class) if len(equiv_class) <= 4 else f"{equiv_class[:3]}..."
                
                status = ""
                if recovered == true_val:
                    correct += 1
                    status = "✓ exact"
                elif true_val in equiv_class:
                    equiv_match += 1
                    status = f"≈ (×{true_val//recovered if recovered > 0 else '?'})"
                
                print(f"w[{row_idx}][{col_idx}]      {recovered:10d} {true_val:8d} {error:8d} {corr:8.4f} {equiv_str:<25} {status}")
                total += 1
    
    print("-" * 80)
    print(f"Exact matches: {correct}/{total} ({100*correct/total:.1f}%)")
    print(f"Equivalence class matches: {equiv_match}/{total} ({100*equiv_match/total:.1f}%)")
    print(f"Total success (exact + equiv): {correct+equiv_match}/{total} ({100*(correct+equiv_match)/total:.1f}%)")
    
    print("\n" + "=" * 60)
    print("ANALYSIS: HW Equivalence Classes")
    print("=" * 60)
    print("Due to HW properties, weights differing by factor of 2 are indistinguishable:")
    print("  HW(w × x) = HW(2w × x) for all x (when no overflow)")
    print()
    print("Recovered weights are BASE values of equivalence classes.")
    print("True weight = recovered × 2^n for some n ≥ 0")
    
    print("\nTrue Weight Matrix (from main.S):")
    for row_idx, row in enumerate(true_weights):
        print(f"  Row {row_idx}: {row}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
