#!/usr/bin/env python3
"""
Adds simplified Hamming Weight and Ham ming Distance leakage counters 
focusing only on key data path signals to avoid massive Verilator expressions.
"""

import sys
import re

def add_simple_counters(filename):
    with open(filename, 'r') as f:
        content = f.read()
    
    # Key signals for AES side-channel analysis (reduced set)
    key_signals = [
        ('data_mem_wdata_o', 32),
        ('data_mem_rdata_i', 32),
        ('data_mem_addr_o', 32),
        ('lsu_wdata_i', 32),
        ('lsu_rdata_o', 32),
        ('rf_wdata_wb_o', 32),
        ('alu_result', 32),
        ('alu_operand_a_ex', 32),
        ('alu_operand_b_ex', 32),
    ]
    
    # Generate HW counter logic
    hw_terms = []
    for sig, width in key_signals:
        hw_terms.append(f"$countones({sig} & {sig}_t0)")
    hw_expr = " +\n    ".join(hw_terms)
    
    hw_counter = f"""
  // Hamming Weight Counter - models static power leakage (# of tainted '1' bits)
  wire [31:0] hamming_weight_t0 = {hw_expr};
  reg [31:0] hamming_weight_counter_t0 = 32'd0;
  always_ff @(posedge clk_i)
    hamming_weight_counter_t0 <= hamming_weight_counter_t0 + hamming_weight_t0;
"""
    
    # Generate HD counter logic with previous value registers
    hd_regs = []
    hd_terms = []
    for sig, width in key_signals:
        hd_regs.append(f"  reg [{width-1}:0] {sig}_prev = {width}'d0;")
        hd_regs.append(f"  always_ff @(posedge clk_i)")
        hd_regs.append(f"    {sig}_prev <= {sig};")
        hd_terms.append(f"$countones(({sig} ^ {sig}_prev) & {sig}_t0)")
    
    hd_regs_code = "\n".join(hd_regs)
    hd_expr = " +\n    ".join(hd_terms)
    
    hd_counter = f"""
  // Hamming Distance Counter - models dynamic power leakage (bit transitions)
{hd_regs_code}
  
  wire [31:0] hamming_distance_t0 = {hd_expr};
  reg [31:0] hamming_distance_counter_t0 = 32'd0;
  always_ff @(posedge clk_i)
    hamming_distance_counter_t0 <= hamming_distance_counter_t0 + hamming_distance_t0;
"""
    
    # Find the original leakage_counter_t0 and insert before it
    pattern = r'(\s+always_ff\s+@\(posedge\s+clk_i\)\s+leakage_counter_t0\s*<=)'
    match = re.search(pattern, content)
    
    if not match:
        print("ERROR: Could not find leakage_counter_t0 declaration")
        return False
    
    insert_pos = match.start()
    new_content = content[:insert_pos] + hw_counter + hd_counter + content[insert_pos:]
    
    # Write back
    with open(filename, 'w') as f:
        f.write(new_content)
    
    print(f"✓ Added simplified HW and HD counters ({len(key_signals)} signals)")
    print(f"  Tracking: {', '.join([s[0] for s in key_signals][:3])}...")
    return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 add_simple_hw_hd_counters.py <cellift.sv>")
        sys.exit(1)
    
    success = add_simple_counters(sys.argv[1])
    sys.exit(0 if success else 1)
