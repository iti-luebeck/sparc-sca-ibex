#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2024-2026 Andrija Neskovic, University of Luebeck
"""
count_leaky_signals.py — Census of leaky vs. total signals for a workload.

Given one instrumented CellIFT VCD (produced by the run_cellift_fasttrace /
run_cellift_trace simulator, which dumps every *_t0 and *_leak0 shadow), this
script answers: of all the signals in the design, how many ever carry
key-dependent taint, and how many physically leak (toggle while tainted)?

It maps directly onto how SPARC-SCA's TVLA works:

    hamming_weight_counter_t0  = popcount over tainted '1' bits   (HW)
    hamming_distance_counter_t0 = popcount over tainted transitions (HD)
                                = sum of the *_leak0 shadow bits

So a signal CONTRIBUTES TO THE TVLA EVALUATION iff its taint shadow `X_t0` is
ever nonzero (it feeds both HW and HD), and the subset that PHYSICALLY LEAKS is
those whose leakage shadow `X_leak0` ever asserts (tainted AND toggling — the
HD contributors).

Signal populations (deduplicated by full hierarchical path):

    total design signals  = distinct nets carrying a `_t0` shadow
                            (every instrumented net gets exactly one; the 3
                             aggregate `*_counter_t0` outputs are excluded)
    leak-capable signals  = distinct nets carrying a pure `_leak0` shadow
                            (`_t0_leak0` "taint-of-taint" shadows are excluded)
    tainted  (TVLA)       = total signals whose `_t0`   is ever nonzero
    leaking  (HD)         = leak-capable signals whose `_leak0` is ever nonzero

Usage:
    python3 count_leaky_signals.py traces/cellift_scenario_aes128_key1.vcd \
        --out results/leaky_signal_census_aes_key1.json
    # optional independent denominator cross-check from the vanilla VCD:
    python3 count_leaky_signals.py traces/cellift_..._key1.vcd \
        --vanilla traces/vanilla_scenario_aes128_key1.vcd
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Aggregate counter outputs are not design signals — exclude from every census.
AGGREGATE_COUNTERS = (
    "hamming_weight_counter_t0",
    "hamming_distance_counter_t0",
    "leakage_counter_t0",
)

RE_VECTOR = re.compile(r'^[bBrR]([0-9a-fA-FxzXZ]+)\s+(.+)$')
RE_SCALAR = re.compile(r'^([01xzXZ])(.+)$')


def classify(name):
    """Return 'leak0' | 't0' | 'functional', and the base (un-suffixed) name.

    `_t0_leak0` (taint-of-taint) is treated as neither a design taint shadow nor
    a leakage shadow — it is redundant book-keeping and is dropped by returning
    kind 'skip'.
    """
    if name.endswith("_t0_leak0"):
        return "skip", None
    if name.endswith("_leak0"):
        return "leak0", name[: -len("_leak0")]
    if name.endswith("_t0"):
        if name in AGGREGATE_COUNTERS:
            return "skip", None
        return "t0", name[: -len("_t0")]
    return "functional", name


def census(vcd_path, want_active=True):
    """Single streaming pass over a VCD.

    Returns a dict of distinct-signal populations. When want_active is True we
    also scan the value-change body and record which `_t0` / `_leak0` signals are
    ever nonzero across the whole trace.
    """
    # full_path -> width, per kind (deduplicated by hierarchical path)
    t0_sig = {}      # base full_path -> width   (design signals)
    leak_sig = {}    # base full_path -> width   (leak-capable signals)
    func_paths = set()
    func_bits = 0

    # vcd id -> ('t0'|'leak0', base_full_path)   (only the kinds we scan)
    id_kind = {}
    t0_active = set()    # base_full_path
    leak_active = set()  # base_full_path

    scope_stack = []
    in_header = True

    print(f"  scanning {vcd_path} ...", flush=True)
    with open(vcd_path, "r", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue

            if in_header:
                if line.startswith("$scope"):
                    p = line.split()
                    if len(p) >= 3:
                        scope_stack.append(p[2])
                elif line.startswith("$upscope"):
                    if scope_stack:
                        scope_stack.pop()
                elif line.startswith("$var"):
                    # $var wire 32 mo9! data_mem_wdata_o_t0 $end
                    # $var wire 128 ro9! crash_dump_o_leak0 [127:0] $end
                    p = line.split()
                    if len(p) >= 5:
                        width = int(p[2])
                        vid = p[3]
                        name = p[4]
                        kind, base = classify(name)
                        if kind == "skip":
                            continue
                        full = ".".join(scope_stack + ([base] if base else [name]))
                        if kind == "t0":
                            t0_sig[full] = width
                            id_kind[vid] = ("t0", full)
                        elif kind == "leak0":
                            leak_sig[full] = width
                            id_kind[vid] = ("leak0", full)
                        else:  # functional
                            fp = ".".join(scope_stack + [name])
                            if fp not in func_paths:
                                func_paths.add(fp)
                                func_bits += width
                elif "$enddefinitions" in line:
                    in_header = False
                    if not want_active:
                        break
                continue

            # ---- value-change body ----
            c0 = line[0]
            if c0 in "bBrR":
                m = RE_VECTOR.match(line)
                if not m:
                    continue
                val_str, vid = m.group(1), m.group(2)
                ent = id_kind.get(vid)
                if ent is None:
                    continue
                # nonzero iff any '1' bit (x/z treated as 0, matching the
                # framework's leakage_signals.py parser)
                if "1" in val_str:
                    (t0_active if ent[0] == "t0" else leak_active).add(ent[1])
            elif c0 in "01xzXZ":
                vid = line[1:]
                ent = id_kind.get(vid)
                if ent is None:
                    continue
                if c0 == "1":
                    (t0_active if ent[0] == "t0" else leak_active).add(ent[1])
            # '#' timestamps and directives are ignored

    return {
        "t0_sig": t0_sig,
        "leak_sig": leak_sig,
        "func_count": len(func_paths),
        "func_bits": func_bits,
        "t0_active": t0_active,
        "leak_active": leak_active,
    }


def bits(sig_map, subset=None):
    if subset is None:
        return sum(sig_map.values())
    return sum(w for s, w in sig_map.items() if s in subset)


def pct(a, b):
    return (100.0 * a / b) if b else 0.0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("vcd", help="Instrumented CellIFT VCD (with *_t0/*_leak0 shadows)")
    ap.add_argument("--vanilla", help="Optional vanilla VCD for an independent "
                                      "functional-signal-count cross-check")
    ap.add_argument("--out", help="Write the census as JSON to this path")
    ap.add_argument("--list-leaking", type=int, default=40, metavar="K",
                    help="Print up to K leaking signal names (default 40; 0 = none)")
    args = ap.parse_args()

    if not Path(args.vcd).exists():
        sys.exit(f"VCD not found: {args.vcd}")

    c = census(args.vcd, want_active=True)

    n_total = len(c["t0_sig"])
    n_regs = len(c["leak_sig"])
    n_taint = len(c["t0_active"])
    n_leak = len(c["leak_active"])

    b_total = bits(c["t0_sig"])
    b_regs = bits(c["leak_sig"])
    b_taint = bits(c["t0_sig"], c["t0_active"])
    b_leak = bits(c["leak_sig"], c["leak_active"])

    vanilla_func = None
    if args.vanilla and Path(args.vanilla).exists():
        vc = census(args.vanilla, want_active=False)
        vanilla_func = {"count": vc["func_count"], "bits": vc["func_bits"]}

    # ---- report ----
    W = 64
    print("\n" + "=" * W)
    print("  Leaky-signal census — " + args.vcd)
    print("=" * W)
    print(f"  {'Population':<46}{'Signals':>9}{'Bits':>9}")
    print(f"  {'-'*46}{'-'*9}{'-'*9}")
    print(f"  {'Total design signals (distinct _t0 nets)':<46}{n_total:>9}{b_total:>9}")
    print(f"  {'  + tainted  (ever _t0!=0, feeds HW & HD/TVLA)':<46}{n_taint:>9}{b_taint:>9}")
    print(f"  {'Leak-capable signals (distinct _leak0 nets)':<46}{n_regs:>9}{b_regs:>9}")
    print(f"  {'  + leaking  (ever _leak0!=0, tainted+toggling)':<46}{n_leak:>9}{b_leak:>9}")
    print("=" * W)
    print("  Ratios:")
    print(f"    tainted / total signals      : {n_taint}/{n_total}"
          f"  = {pct(n_taint, n_total):.1f}%   ({b_taint}/{b_total} bits = {pct(b_taint, b_total):.1f}%)")
    print(f"    leaking / leak-capable       : {n_leak}/{n_regs}"
          f"  = {pct(n_leak, n_regs):.1f}%   ({b_leak}/{b_regs} bits = {pct(b_leak, b_regs):.1f}%)")
    print(f"    leaking / total signals      : {n_leak}/{n_total}"
          f"  = {pct(n_leak, n_total):.1f}%   ({b_leak}/{b_total} bits = {pct(b_leak, b_total):.1f}%)")
    if vanilla_func is not None:
        print(f"  Cross-check: vanilla VCD functional nets = {vanilla_func['count']}"
              f" ({vanilla_func['bits']} bits)")
    print("=" * W)

    leaking_sorted = sorted(c["leak_active"])
    if args.list_leaking and leaking_sorted:
        print(f"\n  Leaking signals ({n_leak} total"
              f"{', showing first %d' % args.list_leaking if n_leak > args.list_leaking else ''}):")
        for s in leaking_sorted[: args.list_leaking]:
            print(f"    {c['leak_sig'].get(s, '?'):>4}b  {s}")

    if args.out:
        out = {
            "vcd": args.vcd,
            "totals": {
                "design_signals": n_total, "design_bits": b_total,
                "leak_capable_signals": n_regs, "leak_capable_bits": b_regs,
            },
            "active": {
                "tainted_signals": n_taint, "tainted_bits": b_taint,
                "leaking_signals": n_leak, "leaking_bits": b_leak,
            },
            "ratios": {
                "tainted_over_total_signals": pct(n_taint, n_total) / 100.0,
                "leaking_over_leak_capable": pct(n_leak, n_regs) / 100.0,
                "leaking_over_total_signals": pct(n_leak, n_total) / 100.0,
            },
            "vanilla_functional": vanilla_func,
            "leaking_signal_names": leaking_sorted,
            "tainted_signal_names": sorted(c["t0_active"]),
        }
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, indent=2))
        print(f"\n  JSON written -> {p}")


if __name__ == "__main__":
    main()
