#!/usr/bin/env python3
"""
Add Hamming Weight and Hamming Distance leakage counters to CellIFT-instrumented design.

This script processes the generated cellift.sv file and adds two additional counters:
1. Hamming Weight Counter: Tracks the number of '1' bits in tainted data (static power model)
2. Hamming Distance Counter: Tracks bit transitions in tainted data (dynamic power model)

These counters provide data-dependent leakage metrics for TVLA analysis.
"""

import re
import sys
from pathlib import Path


def find_data_signals(verilog_content):
    """
    Find all data bus signals and their widths in the design.
    Returns dict of signal_name -> (width, has_taint_version)
    """
    signals = {}
    
    # Look for wire/reg declarations
    # Pattern: wire [width-1:0] signal_name
    wire_pattern = r'(?:wire|reg|logic)\s+(?:\[(\d+):0\])?\s+(\w+);'
    
    for match in re.finditer(wire_pattern, verilog_content):
        width_str, signal_name = match.groups()
        width = int(width_str) + 1 if width_str else 1
        
        # Check if this is a data signal (not a taint signal itself)
        if not signal_name.endswith('_t0') and not signal_name.endswith('_leak0'):
            # Check if it has a corresponding _t0 taint signal
            taint_name = signal_name + '_t0'
            has_taint = taint_name in verilog_content
            
            # Focus on multi-bit data signals that have taint
            if width > 1 and has_taint:
                signals[signal_name] = (width, has_taint)
    
    return signals


def generate_hw_counter_logic(data_signals):
    """
    Generate Verilog code for Hamming Weight counter.
    Sums popcount(data & taint) across all tainted data signals.
    """
    lines = []
    lines.append("  // Hamming Weight counter: counts '1' bits in tainted data")
    lines.append("  // This models static power consumption")
    
    # For each data signal, compute popcount when taint is present
    hw_terms = []
    for signal_name, (width, _) in sorted(data_signals.items()):
        taint_signal = f"{signal_name}_t0"
        # Use $countones for each bit that is both 1 and tainted
        # For multi-bit signals, we count 1s in (data & taint)
        hw_terms.append(f"$countones({signal_name} & {taint_signal})")
    
    # Build the sum expression
    if hw_terms:
        hw_sum = " + ".join(hw_terms)
        lines.append(f"  wire [31:0] hamming_weight_t0 = {hw_sum};")
    else:
        lines.append("  wire [31:0] hamming_weight_t0 = 32'd0;")
    
    # Add counter register
    lines.append("  reg [31:0] hamming_weight_counter_t0 = 32'd0;")
    lines.append("  always_ff @(posedge clk_i)")
    lines.append("    hamming_weight_counter_t0 <= hamming_weight_counter_t0 + hamming_weight_t0;")
    
    return "\n".join(lines)


def generate_hd_counter_logic(data_signals):
    """
    Generate Verilog code for Hamming Distance counter.
    Tracks bit flips in tainted data between consecutive cycles.
    """
    lines = []
    lines.append("  // Hamming Distance counter: counts bit transitions in tainted data")
    lines.append("  // This models dynamic/switching power consumption")
    
    # Need to store previous values for each data signal
    prev_regs = []
    for signal_name, (width, _) in sorted(data_signals.items()):
        prev_regs.append(f"  reg [{width-1}:0] {signal_name}_prev = {width}'d0;")
        prev_regs.append(f"  always_ff @(posedge clk_i)")
        prev_regs.append(f"    {signal_name}_prev <= {signal_name};")
    
    lines.extend(prev_regs)
    lines.append("")
    
    # For each data signal, compute popcount of XOR (bit flips) when taint is present
    hd_terms = []
    for signal_name, (width, _) in sorted(data_signals.items()):
        taint_signal = f"{signal_name}_t0"
        # Count transitions: popcount((current XOR previous) AND taint)
        # Only count transitions in bits that are tainted
        hd_terms.append(f"$countones(({signal_name} ^ {signal_name}_prev) & {taint_signal})")
    
    # Build the sum expression
    if hd_terms:
        hd_sum = " + ".join(hd_terms)
        lines.append(f"  wire [31:0] hamming_distance_t0 = {hd_sum};")
    else:
        lines.append("  wire [31:0] hamming_distance_t0 = 32'd0;")
    
    # Add counter register
    lines.append("  reg [31:0] hamming_distance_counter_t0 = 32'd0;")
    lines.append("  always_ff @(posedge clk_i)")
    lines.append("    hamming_distance_counter_t0 <= hamming_distance_counter_t0 + hamming_distance_t0;")
    
    return "\n".join(lines)


def add_counters_to_module(verilog_path, output_path=None):
    """
    Add HW and HD counters to the top module in the Verilog file.
    """
    if output_path is None:
        output_path = verilog_path
    
    print(f"Reading: {verilog_path}")
    with open(verilog_path, 'r') as f:
        content = f.read()
    
    # Find data signals with taint
    print("Analyzing data signals...")
    data_signals = find_data_signals(content)
    print(f"Found {len(data_signals)} tainted data signals:")
    for sig, (width, _) in list(data_signals.items())[:10]:
        print(f"  {sig} [{width-1}:0]")
    if len(data_signals) > 10:
        print(f"  ... and {len(data_signals) - 10} more")
    
    # Generate counter logic
    print("\nGenerating Hamming Weight counter logic...")
    hw_logic = generate_hw_counter_logic(data_signals)
    
    print("Generating Hamming Distance counter logic...")
    hd_logic = generate_hd_counter_logic(data_signals)
    
    # Find insertion point - look for existing leakage_counter_t0 or end of module
    # Insert before the existing leakage counter if it exists
    insertion_pattern = r'(^\s*always_ff @\(posedge clk_i\)\s*\n\s*leakage_counter_t0)'
    match = re.search(insertion_pattern, content, re.MULTILINE)
    
    if match:
        # Insert before existing leakage counter
        insert_pos = match.start()
        print(f"\nInserting counters before existing leakage_counter_t0 (position {insert_pos})")
    else:
        # Find last always block or end of module
        # Look for the module endmodule to insert before it
        endmodule_pattern = r'\nendmodule'
        matches = list(re.finditer(endmodule_pattern, content))
        if matches:
            # Insert before first endmodule (should be top module)
            insert_pos = matches[0].start()
            print(f"\nInserting counters before endmodule (position {insert_pos})")
        else:
            print("ERROR: Could not find insertion point")
            return False
    
    # Insert the new counter logic
    new_content = (
        content[:insert_pos] + 
        "\n" + 
        hw_logic + 
        "\n\n" + 
        hd_logic + 
        "\n\n" +
        content[insert_pos:]
    )
    
    # Write output
    print(f"\nWriting modified file: {output_path}")
    with open(output_path, 'w') as f:
        f.write(new_content)
    
    # Verify counters were added
    if 'hamming_weight_counter_t0' in new_content and 'hamming_distance_counter_t0' in new_content:
        print("✓ Successfully added HW and HD counters")
        return True
    else:
        print("✗ Failed to add counters")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 add_hw_hd_counters.py <cellift.sv> [output.sv]")
        print("\nAdds Hamming Weight and Hamming Distance counters to CellIFT design.")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path
    
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)
    
    success = add_counters_to_module(input_path, output_path)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
