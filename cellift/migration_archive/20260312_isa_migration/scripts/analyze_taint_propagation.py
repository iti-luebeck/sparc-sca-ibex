#!/usr/bin/env python3
"""
CellIFT Taint Propagation Analyzer

This script analyzes FST/VCD trace files from CellIFT simulations to extract
the list of hardware modules/cells that become tainted during execution.

Usage:
    python analyze_taint_propagation.py <trace_file.fst> [--output report.txt]

The script identifies signals with the '_t0' suffix (CellIFT taint markers)
and reports which hardware elements become tainted at what cycle.
"""

import argparse
import subprocess
import tempfile
import os
import re
import sys
from collections import defaultdict


def fst_to_vcd(fst_file, vcd_file=None):
    """Convert FST trace to VCD format for easier parsing."""
    if vcd_file is None:
        vcd_file = fst_file.replace('.fst', '.vcd')
    
    print(f"Converting {fst_file} to VCD format...")
    result = subprocess.run(['fst2vcd', fst_file, '-o', vcd_file], 
                          capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error converting FST to VCD: {result.stderr}")
        return None
    return vcd_file


def extract_taint_signals_from_hier(hier_file):
    """Extract taint signal names from the FST hierarchy file."""
    taint_signals = []
    all_signals = []
    
    if not os.path.exists(hier_file):
        print(f"Hierarchy file {hier_file} not found")
        return taint_signals, all_signals
    
    print(f"Reading hierarchy file: {hier_file}")
    
    with open(hier_file, 'r', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if '_t0' in line:
                taint_signals.append(line)
            if line:
                all_signals.append(line)
    
    return taint_signals, all_signals


def analyze_vcd_file(vcd_file):
    """
    Parse VCD file and find signals that become tainted (non-zero).
    Returns a dictionary mapping cycle -> list of newly tainted signals.
    """
    tainted_signals = {}
    signal_map = {}  # VCD identifier -> signal name
    current_time = 0
    ever_tainted = set()  # Track signals that were ever tainted
    first_taint_time = {}  # Signal -> first time it became tainted
    
    print(f"Analyzing VCD file: {vcd_file}")
    
    try:
        with open(vcd_file, 'r') as f:
            in_header = True
            current_scope = []
            
            for line in f:
                line = line.strip()
                
                if line.startswith('$scope'):
                    # Parse: $scope module name $end
                    parts = line.split()
                    if len(parts) >= 3:
                        scope_name = parts[2]
                        current_scope.append(scope_name)
                
                elif line.startswith('$upscope'):
                    if current_scope:
                        current_scope.pop()
                
                elif line.startswith('$var'):
                    # Parse: $var wire 1 id name $end
                    parts = line.split()
                    if len(parts) >= 5:
                        var_id = parts[3]
                        var_name = parts[4]
                        # Remove array indices for cleaner names
                        var_name = re.sub(r'\[\d+:\d+\]$', '', var_name)
                        full_name = '.'.join(current_scope + [var_name])
                        signal_map[var_id] = full_name
                
                elif line.startswith('$enddefinitions'):
                    in_header = False
                    print(f"Found {len(signal_map)} signals in VCD file")
                
                elif not in_header:
                    if line.startswith('#'):
                        # Time change
                        current_time = int(line[1:])
                    
                    elif line and not line.startswith('$'):
                        # Value change
                        # Binary: 0/1/x/z followed by identifier
                        # Multi-bit: b<bits> <identifier>
                        
                        if line.startswith('b') or line.startswith('B'):
                            # Multi-bit value
                            parts = line.split()
                            if len(parts) >= 2:
                                value = parts[0][1:]  # Remove 'b' prefix
                                var_id = parts[1]
                                
                                # Check if this is a taint signal and if it's non-zero
                                if var_id in signal_map:
                                    sig_name = signal_map[var_id]
                                    if '_t0' in sig_name:
                                        # Check if any bit is 1 (tainted)
                                        if '1' in value:
                                            if sig_name not in ever_tainted:
                                                ever_tainted.add(sig_name)
                                                first_taint_time[sig_name] = current_time
                        
                        elif len(line) >= 2:
                            # Single-bit value
                            value = line[0]
                            var_id = line[1:]
                            
                            if var_id in signal_map:
                                sig_name = signal_map[var_id]
                                if '_t0' in sig_name and value == '1':
                                    if sig_name not in ever_tainted:
                                        ever_tainted.add(sig_name)
                                        first_taint_time[sig_name] = current_time
    
    except Exception as e:
        print(f"Error parsing VCD file: {e}")
        return {}, {}, set()
    
    return signal_map, first_taint_time, ever_tainted


def group_by_module(signals):
    """Group signals by their parent module."""
    modules = defaultdict(list)
    
    for sig in signals:
        parts = sig.rsplit('.', 1)
        if len(parts) == 2:
            module_path = parts[0]
            signal_name = parts[1]
        else:
            module_path = "TOP"
            signal_name = sig
        
        modules[module_path].append(signal_name)
    
    return modules


def generate_report(ever_tainted, first_taint_time, output_file=None, full_output=False):
    """Generate a human-readable report of tainted hardware elements."""
    
    # Limits for truncated output
    sig_limit = None if full_output else 20
    timeline_limit = None if full_output else 50
    hierarchy_limit = None if full_output else 30
    
    # Group by module
    modules = group_by_module(ever_tainted)
    
    # Sort signals by first taint time
    sorted_by_time = sorted(first_taint_time.items(), key=lambda x: x[1])
    
    report = []
    report.append("=" * 80)
    report.append("CellIFT Taint Propagation Analysis Report")
    report.append("=" * 80)
    report.append("")
    report.append(f"Total tainted signals: {len(ever_tainted)}")
    report.append(f"Total tainted modules: {len(modules)}")
    report.append("")
    
    # Summary by module
    report.append("-" * 80)
    report.append("TAINTED MODULES SUMMARY (sorted by number of tainted signals)")
    report.append("-" * 80)
    
    sorted_modules = sorted(modules.items(), key=lambda x: len(x[1]), reverse=True)
    for module, signals in sorted_modules:
        # Remove _t0 suffix from signal names for cleaner display
        clean_signals = [s.replace('_t0', '') for s in signals]
        report.append(f"\n{module}:")
        report.append(f"  Tainted signals ({len(signals)}):")
        display_signals = sorted(clean_signals)[:sig_limit] if sig_limit else sorted(clean_signals)
        for sig in display_signals:
            report.append(f"    - {sig}")
        if sig_limit and len(clean_signals) > sig_limit:
            report.append(f"    ... and {len(clean_signals) - sig_limit} more")
    
    # Timeline of taint propagation
    report.append("")
    report.append("-" * 80)
    if timeline_limit:
        report.append(f"TAINT PROPAGATION TIMELINE (first {timeline_limit} signals)")
    else:
        report.append("TAINT PROPAGATION TIMELINE (all signals)")
    report.append("-" * 80)
    
    current_time = -1
    display_timeline = sorted_by_time[:timeline_limit] if timeline_limit else sorted_by_time
    for sig, time in display_timeline:
        if time != current_time:
            current_time = time
            report.append(f"\n[Cycle {time}]:")
        # Clean up signal name
        clean_sig = sig.replace('_t0', '')
        report.append(f"  → {clean_sig}")
    
    if timeline_limit and len(sorted_by_time) > timeline_limit:
        report.append(f"\n... and {len(sorted_by_time) - timeline_limit} more signals")
    
    # Module hierarchy summary
    report.append("")
    report.append("-" * 80)
    report.append("HARDWARE MODULE HIERARCHY WITH TAINT")
    report.append("-" * 80)
    
    # Extract unique module paths at different hierarchy levels
    module_hierarchy = defaultdict(set)
    for module in modules.keys():
        parts = module.split('.')
        for i in range(1, len(parts) + 1):
            parent = '.'.join(parts[:i])
            module_hierarchy[parent].add(module)
    
    # Print top-level modules
    top_level = sorted([m for m in module_hierarchy.keys() if m.count('.') <= 2])
    display_hierarchy = top_level[:hierarchy_limit] if hierarchy_limit else top_level
    for module in display_hierarchy:
        count = sum(len(modules[m]) for m in module_hierarchy[module])
        report.append(f"  {module}: {count} tainted signals")
    
    if hierarchy_limit and len(top_level) > hierarchy_limit:
        report.append(f"  ... and {len(top_level) - hierarchy_limit} more modules")
    
    report_text = '\n'.join(report)
    
    if output_file:
        with open(output_file, 'w') as f:
            f.write(report_text)
        print(f"\nReport saved to: {output_file}")
    
    return report_text


def use_fstminer(fst_file):
    """Use fstminer to extract signal information from FST file."""
    print(f"Using fstminer to analyze {fst_file}...")
    
    # Get list of signals with non-zero values
    result = subprocess.run(
        ['fstminer', fst_file, '--nonzero'],
        capture_output=True, text=True, timeout=300
    )
    
    taint_signals = []
    for line in result.stdout.split('\n'):
        if '_t0' in line:
            taint_signals.append(line.strip())
    
    return taint_signals


def main():
    parser = argparse.ArgumentParser(
        description='Analyze CellIFT taint propagation from FST/VCD traces'
    )
    parser.add_argument('trace_file', help='Path to FST or VCD trace file')
    parser.add_argument('--output', '-o', help='Output report file', 
                       default='taint_report.txt')
    parser.add_argument('--full', '-f', action='store_true',
                       help='Show all signals without truncation')
    parser.add_argument('--keep-vcd', action='store_true', 
                       help='Keep intermediate VCD file')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.trace_file):
        print(f"Error: Trace file not found: {args.trace_file}")
        sys.exit(1)
    
    # Check file size
    file_size = os.path.getsize(args.trace_file)
    if file_size < 1000:
        print(f"Warning: Trace file is very small ({file_size} bytes)")
        print("The simulation may not have run long enough to produce meaningful data.")
    
    # Check for hierarchy file
    hier_file = args.trace_file + '.hier'
    if os.path.exists(hier_file):
        taint_signals, all_signals = extract_taint_signals_from_hier(hier_file)
        print(f"Found {len(taint_signals)} taint signals in hierarchy")
        print(f"Total signals in design: {len(all_signals)}")
    
    # Convert FST to VCD if needed
    vcd_file = args.trace_file
    if args.trace_file.endswith('.fst'):
        vcd_file = fst_to_vcd(args.trace_file)
        if not vcd_file:
            print("Failed to convert FST to VCD, trying fstminer...")
            taint_signals = use_fstminer(args.trace_file)
            print(f"\nTaint signals found by fstminer: {len(taint_signals)}")
            for sig in taint_signals[:50]:
                print(f"  {sig}")
            sys.exit(0)
    
    # Analyze the VCD file
    signal_map, first_taint_time, ever_tainted = analyze_vcd_file(vcd_file)
    
    if not ever_tainted:
        print("\nNo tainted signals found in the trace.")
        print("This could mean:")
        print("  1. The simulation didn't run long enough")
        print("  2. The taint wasn't properly initialized")
        print("  3. The taint signals have different naming convention")
        
        # List all taint-related signals from the signal map
        print("\nAll signals containing '_t0' in the design:")
        taint_sigs = [s for s in signal_map.values() if '_t0' in s]
        for sig in sorted(taint_sigs)[:30]:
            print(f"  {sig}")
        if len(taint_sigs) > 30:
            print(f"  ... and {len(taint_sigs) - 30} more")
    else:
        # Generate report
        report = generate_report(ever_tainted, first_taint_time, args.output, args.full)
        print(report)
    
    # Clean up temporary VCD file
    if not args.keep_vcd and vcd_file != args.trace_file and os.path.exists(vcd_file):
        os.remove(vcd_file)
        print(f"\nRemoved temporary VCD file: {vcd_file}")


if __name__ == '__main__':
    main()
