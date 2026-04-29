#!/usr/bin/env python3
"""
pc_at_leakage.py — Map CellIFT leakage cycles to CPU instructions.

Parses a vanilla CPU VCD and extracts, at each simulation cycle of
interest, the fetch PC and the instruction at the retirement stage, then
correlates with objdump disassembly and addr2line source-line info.

Timing formula (from testbench.h):
  reset() = tick(1) + tick(kResetLength=5) → 6 pre-loop ticks
  CSV cycle N → VCD posedge time = 5 * (7 + N)   [tick_count_ = 7+N]

Usage:
    python3 pc_at_leakage.py <vcd> <elf> [options]

    --cycles N [N ...]    Cycles to inspect (default: 30-50)
    --objdump  PATH       riscv64-unknown-elf-objdump / riscv32-unknown-elf-objdump (auto-detected)
    --addr2line PATH      riscv64-unknown-elf-addr2line / riscv32-unknown-elf-addr2line (auto-detected)
    --no-source           Skip source-line lookup
    --tick-base N         Pre-loop tick count (default: 7)
"""

import argparse
import os
import re
import json
import shutil
import subprocess
import sys
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# Timing
# ──────────────────────────────────────────────────────────────────────────────
TICK_BASE   = 7   # 1 assert-reset tick + 5 kResetLength ticks + loop starts
TICK_PERIOD = 5   # VCD time units per clock cycle


def cycle_to_vcd_time(cycle: int, tick_base: int = TICK_BASE) -> int:
    """Return VCD posedge timestamp for CSV cycle N."""
    return TICK_PERIOD * (tick_base + cycle)


# ──────────────────────────────────────────────────────────────────────────────
# Signals of interest (local name inside PIPELINE_SCOPE)
# ──────────────────────────────────────────────────────────────────────────────
# Optional scope filter. If set, any matching scope containing this string
# is eligible; if unset, best-matching candidates are selected globally.
PIPELINE_SCOPE = os.environ.get("PIPELINE_SCOPE", "")

# Maps VCD signal name → logical tag
SIGNALS_WANTED = {
    "PcManager_pc":                        "fetch_pc",
    "decode_out_PC":                       "decode_pc",
    "retirementStage_in_PC":               "retire_pc",
    "retirementStage_in_IR":               "retire_ir",
    "retirementStage_arbitration_isDone":  "retire_done",
    "retirementStage_arbitration_isValid": "retire_valid",
    "Scheduler_rob_willRetire":            "will_retire",
    # Ibex-friendly fallbacks
    "pc_if":                               "fetch_pc",
    "pc_id":                               "decode_pc",
    "pc_wb":                               "retire_pc",
    "instr_rdata_id":                      "retire_ir",
    "instr_valid_id":                      "retire_valid",
    "current_pc":                          "fetch_pc",
    "next_pc":                             "decode_pc",
    "instr_done_wb":                       "will_retire",
}


# ──────────────────────────────────────────────────────────────────────────────
# VCD parser  — samples named signals at specific timestamps
# ──────────────────────────────────────────────────────────────────────────────

def parse_vcd(path: str, target_times: set, tick_base: int) -> dict:
    """
    Stream-parse the VCD; take a snapshot of SIGNALS_WANTED at every
    target VCD time.  Returns {vcd_time: {logical_tag: int_value | None}}.

    Convention: values are captured *after* all value-changes at that
    timestamp have been applied (i.e. the stable post-edge state).
    """
    id_to_tag = {}   # vcd_id → logical tag
    tag_to_choice = {}  # logical tag → (score, vcd_id)
    scope_stack = []
    buf, kw = [], None
    in_defs = True

    cur_vals = {}       # id → last int value seen
    cur_time = 0
    snapshots = {}      # vcd_time → {tag: val}

    def scope_score(scope: str, tag: str) -> int:
        score = 0
        # Prefer core internals over wrappers/package scopes.
        if "u_ibex_core" in scope:
            score += 8
        if "id_stage_i" in scope and tag in ("decode_pc", "retire_ir", "retire_valid"):
            score += 6
        if "if_stage_i" in scope and tag == "fetch_pc":
            score += 6
        if "wb_stage_i" in scope and tag in ("retire_pc", "will_retire"):
            score += 6
        if "ibex_core" in scope:
            score += 2
        return score

    def take_snapshot(t):
        snap = {tag: cur_vals.get(vid) for tag, vid in id_to_tag.items()}
        snapshots[t] = snap

    with open(path, "r", errors="replace") as fh:
        for raw in fh:
            # ── Definition section ─────────────────────────────────────────
            if in_defs:
                for tok in raw.split():
                    if tok == "$enddefinitions":
                        in_defs = False
                        break
                    if tok.startswith("$") and tok != "$end":
                        kw = tok; buf = []; continue
                    if tok == "$end":
                        if kw == "$scope" and len(buf) >= 2:
                            scope_stack.append(buf[1])
                        elif kw == "$upscope":
                            if scope_stack: scope_stack.pop()
                        elif kw == "$var" and len(buf) >= 4:
                            sc  = ".".join(scope_stack)
                            nm  = buf[3]
                            vid = buf[2]
                            if nm in SIGNALS_WANTED:
                                if PIPELINE_SCOPE and PIPELINE_SCOPE not in sc:
                                    continue
                                tag = SIGNALS_WANTED[nm]
                                score = scope_score(sc, tag)
                                prev = tag_to_choice.get(tag)
                                if prev is None or score > prev[0]:
                                    tag_to_choice[tag] = (score, vid)
                        kw = None; buf = []
                        continue
                    if kw: buf.append(tok)
                continue  # still in header

            if in_defs is False and not id_to_tag and tag_to_choice:
                # Finalize one VCD id per logical tag once definitions end.
                id_to_tag = {tag: choice[1] for tag, choice in tag_to_choice.items()}

            # ── Value-change section ───────────────────────────────────────
            line = raw.strip()
            if not line:
                continue

            # Timestamp
            if line.startswith("#"):
                # Snapshot the *previous* time if it was a target
                if cur_time in target_times:
                    take_snapshot(cur_time)
                cur_time = int(line[1:])
                continue

            # Scalar:  0ID  1ID  xID  zID
            if line[0] in "01xzXZ" and len(line) > 1 and " " not in line:
                vid = line[1:]
                val = 0 if line[0] in "0xXzZ" else 1
                if vid in id_to_tag.values():
                    cur_vals[vid] = val
                continue

            # Vector:  bVALUE ID
            if (line[0] in "bB") and " " in line:
                parts = line.split(None, 1)
                if len(parts) == 2:
                    bval, vid = parts[0], parts[1].strip()
                    if vid in id_to_tag.values():
                        clean = (bval[1:]
                                 .replace("x", "0").replace("X", "0")
                                 .replace("z", "0").replace("Z", "0"))
                        try:
                            cur_vals[vid] = int(clean, 2)
                        except ValueError:
                            cur_vals[vid] = 0
                continue

    # Final snapshot if needed
    if cur_time in target_times:
        take_snapshot(cur_time)

    return snapshots


# ──────────────────────────────────────────────────────────────────────────────
# Disassembly helpers
# ──────────────────────────────────────────────────────────────────────────────

def build_disasm_db(elf: str, objdump: str) -> dict:
    """Return {pc_int: 'mnemonic operands'} from objdump -d."""
    result = subprocess.run(
        [objdump, "-d", "--no-show-raw-insn", elf],
        capture_output=True, text=True,
    )
    db = {}
    for line in result.stdout.splitlines():
        m = re.match(r"\s*([0-9a-fA-F]+):\s+(.+)", line)
        if m:
            db[int(m.group(1), 16)] = m.group(2).strip()
    return db


def addr2line_lookup(elf: str, bin_: str, pc: int) -> str:
    """Return 'function  file:line' from addr2line, or '' on failure."""
    try:
        r = subprocess.run(
            [bin_, "-e", elf, "-f", "-i", hex(pc)],
            capture_output=True, text=True, timeout=5,
        )
        lines = [l.strip() for l in r.stdout.splitlines() if l.strip()]
        return "  ".join(lines) if lines else ""
    except Exception:
        return ""


def find_tool(name: str) -> str:
    """Search PATH and common install prefixes for a RISC-V tool."""
    in_path = shutil.which(name)
    if in_path:
        return in_path

    riscv_prefix = os.environ.get("RISCV", "")
    candidates = [
        f"{riscv_prefix}/bin/{name}" if riscv_prefix else None,
        str(Path.home() / "prefix-cellift" / "riscv" / "bin" / name),
        f"/mnt/nvme1n1p1/chipyard-1.11.0/.conda-env/riscv-tools/bin/{name}",
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return c
    return name  # let subprocess report a clear error


def find_first_tool(names):
    for name in names:
        candidate = find_tool(name)
        if candidate != name or shutil.which(name):
            return candidate
    return names[0]


# ──────────────────────────────────────────────────────────────────────────────
# Report
# ──────────────────────────────────────────────────────────────────────────────

def print_table(cycles, snapshots, disasm, tick_base):
    W = 42
    print()
    print("─" * 110)
    print(f"  {'Cycle':>5}  {'Fetch PC':>10}  {'Fetch Instruction':<{W}}  "
          f"{'Retire?':>7}  {'Retire PC':>10}  Retire Instruction")
    print("─" * 110)

    for cycle in sorted(cycles):
        t = cycle_to_vcd_time(cycle, tick_base)
        snap = snapshots.get(t, {})

        fetch_pc  = snap.get("fetch_pc")
        retire_pc = snap.get("retire_pc")
        retire_ir = snap.get("retire_ir")
        retiring  = bool(snap.get("retire_done") or snap.get("will_retire"))

        if fetch_pc is not None:
            f_hex   = f"0x{fetch_pc:08x}"
            f_instr = disasm.get(fetch_pc, "?")[:W]
        else:
            f_hex   = "         ?"
            f_instr = ""

        if retiring and retire_pc is not None:
            r_hex   = f"0x{retire_pc:08x}"
            r_instr = disasm.get(retire_pc, "?")
        else:
            r_hex   = ""
            r_instr = "(not retiring)"

        print(f"  {cycle:>5}  {f_hex:>10}  {f_instr:<{W}}  "
              f"{'YES' if retiring else 'no':>7}  {r_hex:>10}  {r_instr}")


def print_source_table(cycles, snapshots, disasm, elf, addr2line_bin, tick_base):
    """Show source-line info for every unique fetch PC in the cycle range."""
    print()
    print("─" * 100)
    print("  Source-line correlation  (fetch PCs at each leakage cycle)")
    print("─" * 100)
    print(f"  {'Cycle':>5}  {'Fetch PC':>10}  {'Instruction':<42}  Source")
    print("─" * 100)

    seen = {}  # pc → src string (cache addr2line calls)
    for cycle in sorted(cycles):
        t    = cycle_to_vcd_time(cycle, tick_base)
        snap = snapshots.get(t, {})
        fp   = snap.get("fetch_pc")
        if fp is None:
            print(f"  {cycle:>5}  {'?':>10}")
            continue
        if fp not in seen:
            seen[fp] = addr2line_lookup(elf, addr2line_bin, fp)
        instr = disasm.get(fp, "?")[:42]
        print(f"  {cycle:>5}  0x{fp:08x}  {instr:<42}  {seen[fp]}")


def build_instruction_json(cycles, snapshots, disasm, elf, addr2line_bin, tick_base, include_source):
    """Build structured per-cycle instruction attribution data."""
    rows = []
    src_cache = {}
    for cycle in sorted(cycles):
        t = cycle_to_vcd_time(cycle, tick_base)
        snap = snapshots.get(t, {})
        fetch_pc = snap.get("fetch_pc")
        retire_pc = snap.get("retire_pc")
        retiring = bool(snap.get("retire_done") or snap.get("will_retire"))

        fetch_instr = disasm.get(fetch_pc, "?") if fetch_pc is not None else None
        retire_instr = disasm.get(retire_pc, "?") if (retire_pc is not None and retiring) else None

        source = None
        if include_source and fetch_pc is not None:
            if fetch_pc not in src_cache:
                src_cache[fetch_pc] = addr2line_lookup(elf, addr2line_bin, fetch_pc)
            source = src_cache.get(fetch_pc)

        rows.append({
            "cycle": int(cycle),
            "vcd_time": int(t),
            "fetch": {
                "pc": (f"0x{fetch_pc:08x}" if fetch_pc is not None else None),
                "instruction": fetch_instr,
                "source": source,
            },
            "retire": {
                "retiring": bool(retiring),
                "pc": (f"0x{retire_pc:08x}" if retire_pc is not None else None),
                "instruction": retire_instr,
            }
        })

    return {
        "metadata": {
            "tick_base": int(tick_base),
            "tick_period": int(TICK_PERIOD),
            "formula": "vcd_time = tick_period * (tick_base + cycle)",
            "vcd": None,
            "elf": str(elf),
        },
        "cycles": rows,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Map CellIFT leakage cycles to CPU instructions via vanilla VCD + objdump",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("vcd",  help="Vanilla Ibex/CPU VCD file")
    ap.add_argument("elf",  help="RISC-V ELF binary (same scenario as VCD)")
    ap.add_argument("--cycles", nargs="+", type=int,
                    default=list(range(30, 55)),
                    metavar="N",
                    help="Simulation cycles to inspect (default: 30-54)")
    ap.add_argument("--objdump",    default=None,
                    help="riscv64-unknown-elf-objdump (or riscv32-unknown-elf-objdump) path (auto-detected)")
    ap.add_argument("--addr2line",  default=None,
                    help="riscv64-unknown-elf-addr2line (or riscv32-unknown-elf-addr2line) path (auto-detected)")
    ap.add_argument("--no-source",  action="store_true",
                    help="Skip addr2line source-line lookup")
    ap.add_argument("--tick-base",  type=int, default=TICK_BASE,
                    help=f"Pre-loop tick count (default: {TICK_BASE})")
    ap.add_argument("--out-json", default=None,
                    help="Optional JSON output path for per-cycle instruction mapping")
    args = ap.parse_args()

    # Populate RISCV if not already set (native without env.sh; noop in Docker).
    if not os.environ.get("RISCV"):
        _script_dir = Path(__file__).resolve().parent
        source_env = _script_dir / ".." / ".." / ".." / "env.sh"
        source_env = source_env.resolve()
        if source_env.exists():
            result = subprocess.run(
                ["bash", "-c", f"source {source_env} 2>/dev/null; echo $RISCV"],
                capture_output=True, text=True,
            )
            riscv = result.stdout.strip()
            if riscv:
                os.environ["RISCV"] = riscv

    objdump_bin = args.objdump or find_first_tool([
        "riscv64-unknown-elf-objdump",
        "riscv32-unknown-elf-objdump",
    ])
    addr2line_bin = args.addr2line or find_first_tool([
        "riscv64-unknown-elf-addr2line",
        "riscv32-unknown-elf-addr2line",
    ])

    # ── Build disassembly index ───────────────────────────────────────────────
    print(f"Loading disassembly from: {args.elf}")
    disasm = build_disasm_db(args.elf, objdump_bin)
    print(f"  {len(disasm):,} instructions indexed")

    # ── Determine VCD times to sample ────────────────────────────────────────
    target_times = {cycle_to_vcd_time(c, args.tick_base) for c in args.cycles}
    print(f"Parsing VCD: {args.vcd}")
    print(f"  Cycles {min(args.cycles)}–{max(args.cycles)} "
          f"→ VCD times {min(target_times)}–{max(target_times)}")

    # ── Parse VCD ────────────────────────────────────────────────────────────
    snapshots = parse_vcd(args.vcd, target_times, args.tick_base)
    print(f"  Captured {len(snapshots)} snapshots  "
          f"(signals found: {len({v for s in snapshots.values() for v in s if s[v] is not None})})")

    # ── Print fetch / retire table ────────────────────────────────────────────
    print_table(args.cycles, snapshots, disasm, args.tick_base)

    # ── Print source-line correlation ─────────────────────────────────────────
    if not args.no_source:
        print_source_table(args.cycles, snapshots, disasm,
                           args.elf, addr2line_bin, args.tick_base)

    if args.out_json:
        data = build_instruction_json(
            args.cycles,
            snapshots,
            disasm,
            args.elf,
            addr2line_bin,
            args.tick_base,
            include_source=(not args.no_source),
        )
        data["metadata"]["vcd"] = str(args.vcd)
        out_path = Path(args.out_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(data, indent=2))
        print(f"\nInstruction JSON -> {out_path}")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
