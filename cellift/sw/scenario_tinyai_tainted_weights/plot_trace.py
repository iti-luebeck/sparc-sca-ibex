#!/usr/bin/env python3
"""
Plot Hamming Distance (HD) or Hamming Weight (HW) traces from WAL++ CSV output.

Usage:
    python3 plot_trace.py trace_hd.csv -o trace_hd.png
    python3 plot_trace.py trace_hw.csv -o trace_hw.png
    python3 plot_trace.py trace_hd.csv --title "Custom Title" -o plot.png
"""

import argparse
import sys
import os

def main():
    parser = argparse.ArgumentParser(
        description='Plot HD/HW traces from WAL++ CSV output'
    )
    parser.add_argument('input', help='Input CSV file (HD or HW trace)')
    parser.add_argument('-o', '--output', required=True,
                        help='Output plot file (PNG, PDF, etc.)')
    parser.add_argument('--title', help='Custom plot title')
    parser.add_argument('--xlabel', default='Cycle',
                        help='X-axis label (default: Cycle)')
    parser.add_argument('--ylabel', help='Y-axis label (auto-detected from filename)')
    parser.add_argument('--figsize', nargs=2, type=float, default=[12, 6],
                        help='Figure size (width height), default: 12 6')
    parser.add_argument('--dpi', type=int, default=150,
                        help='Output DPI (default: 150)')
    parser.add_argument('--no-grid', action='store_true',
                        help='Disable grid')
    parser.add_argument('--color', default='steelblue',
                        help='Line color (default: steelblue)')
    parser.add_argument('--linewidth', type=float, default=0.5,
                        help='Line width (default: 0.5)')
    
    args = parser.parse_args()
    
    # Check input file exists
    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    
    # Import matplotlib (do late import for faster --help)
    try:
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError as e:
        print(f"Error: Missing required package: {e}", file=sys.stderr)
        print("Install with: pip install matplotlib numpy", file=sys.stderr)
        sys.exit(1)
    
    # Read CSV data
    try:
        # WAL++ CSV format: typically just values, one per line
        # Or it could be cycle,value pairs
        data = []
        with open(args.input, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # Handle both single column and multi-column formats
                parts = line.split(',')
                if len(parts) >= 2:
                    # Assume last column is the value we want
                    try:
                        data.append(float(parts[-1]))
                    except ValueError:
                        continue
                else:
                    try:
                        data.append(float(parts[0]))
                    except ValueError:
                        continue
        
        if not data:
            print(f"Error: No valid data found in {args.input}", file=sys.stderr)
            sys.exit(1)
        
        data = np.array(data)
        
    except Exception as e:
        print(f"Error reading CSV: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Auto-detect type from filename
    basename = os.path.basename(args.input)
    if '_hd' in basename.lower():
        trace_type = 'HD'
        default_ylabel = 'Hamming Distance'
        default_color = 'steelblue'
    elif '_hw' in basename.lower():
        trace_type = 'HW'
        default_ylabel = 'Hamming Weight'
        default_color = 'darkorange'
    else:
        trace_type = 'Unknown'
        default_ylabel = 'Value'
        default_color = 'steelblue'
    
    # Set up labels
    ylabel = args.ylabel if args.ylabel else default_ylabel
    color = args.color if args.color != 'steelblue' else default_color
    
    # Generate title
    if args.title:
        title = args.title
    else:
        # Extract vector name from filename
        name = os.path.splitext(basename)[0]
        title = f"{trace_type} Trace: {name}"
    
    # Create plot
    fig, ax = plt.subplots(figsize=tuple(args.figsize))
    
    cycles = np.arange(len(data))
    ax.plot(cycles, data, color=color, linewidth=args.linewidth)
    
    ax.set_xlabel(args.xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    
    if not args.no_grid:
        ax.grid(True, alpha=0.3)
    
    # Add statistics annotation
    stats_text = f'Mean: {data.mean():.2f}\nMax: {data.max():.0f}\nMin: {data.min():.0f}'
    ax.text(0.98, 0.98, stats_text, transform=ax.transAxes,
            fontsize=8, verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    
    # Save
    try:
        plt.savefig(args.output, dpi=args.dpi, bbox_inches='tight')
        print(f"Saved: {args.output}")
    except Exception as e:
        print(f"Error saving plot: {e}", file=sys.stderr)
        sys.exit(1)
    
    plt.close()

if __name__ == '__main__':
    main()
