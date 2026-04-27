#!/usr/bin/env python3
"""
hw_model_test.py — Correlate CellIFT HW counter dynamics with AES S-box HW model.

Expected input layout in RESULTS_DIR:
  group_a_000.csv ... group_a_255.csv
  group_b_000.csv ... group_b_255.csv

The script uses per-cycle increments of hamming_weight_counter_t0 and computes,
for every cycle and key hypothesis, Pearson correlation against:
  HW(SBOX(plaintext_byte XOR key_hypothesis))

Plaintexts are read from scenario manifests in sw/_manifests when available.
"""

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


SBOX = np.array([
    0x63, 0x7C, 0x77, 0x7B, 0xF2, 0x6B, 0x6F, 0xC5, 0x30, 0x01, 0x67, 0x2B, 0xFE, 0xD7, 0xAB, 0x76,
    0xCA, 0x82, 0xC9, 0x7D, 0xFA, 0x59, 0x47, 0xF0, 0xAD, 0xD4, 0xA2, 0xAF, 0x9C, 0xA4, 0x72, 0xC0,
    0xB7, 0xFD, 0x93, 0x26, 0x36, 0x3F, 0xF7, 0xCC, 0x34, 0xA5, 0xE5, 0xF1, 0x71, 0xD8, 0x31, 0x15,
    0x04, 0xC7, 0x23, 0xC3, 0x18, 0x96, 0x05, 0x9A, 0x07, 0x12, 0x80, 0xE2, 0xEB, 0x27, 0xB2, 0x75,
    0x09, 0x83, 0x2C, 0x1A, 0x1B, 0x6E, 0x5A, 0xA0, 0x52, 0x3B, 0xD6, 0xB3, 0x29, 0xE3, 0x2F, 0x84,
    0x53, 0xD1, 0x00, 0xED, 0x20, 0xFC, 0xB1, 0x5B, 0x6A, 0xCB, 0xBE, 0x39, 0x4A, 0x4C, 0x58, 0xCF,
    0xD0, 0xEF, 0xAA, 0xFB, 0x43, 0x4D, 0x33, 0x85, 0x45, 0xF9, 0x02, 0x7F, 0x50, 0x3C, 0x9F, 0xA8,
    0x51, 0xA3, 0x40, 0x8F, 0x92, 0x9D, 0x38, 0xF5, 0xBC, 0xB6, 0xDA, 0x21, 0x10, 0xFF, 0xF3, 0xD2,
    0xCD, 0x0C, 0x13, 0xEC, 0x5F, 0x97, 0x44, 0x17, 0xC4, 0xA7, 0x7E, 0x3D, 0x64, 0x5D, 0x19, 0x73,
    0x60, 0x81, 0x4F, 0xDC, 0x22, 0x2A, 0x90, 0x88, 0x46, 0xEE, 0xB8, 0x14, 0xDE, 0x5E, 0x0B, 0xDB,
    0xE0, 0x32, 0x3A, 0x0A, 0x49, 0x06, 0x24, 0x5C, 0xC2, 0xD3, 0xAC, 0x62, 0x91, 0x95, 0xE4, 0x79,
    0xE7, 0xC8, 0x37, 0x6D, 0x8D, 0xD5, 0x4E, 0xA9, 0x6C, 0x56, 0xF4, 0xEA, 0x65, 0x7A, 0xAE, 0x08,
    0xBA, 0x78, 0x25, 0x2E, 0x1C, 0xA6, 0xB4, 0xC6, 0xE8, 0xDD, 0x74, 0x1F, 0x4B, 0xBD, 0x8B, 0x8A,
    0x70, 0x3E, 0xB5, 0x66, 0x48, 0x03, 0xF6, 0x0E, 0x61, 0x35, 0x57, 0xB9, 0x86, 0xC1, 0x1D, 0x9E,
    0xE1, 0xF8, 0x98, 0x11, 0x69, 0xD9, 0x8E, 0x94, 0x9B, 0x1E, 0x87, 0xE9, 0xCE, 0x55, 0x28, 0xDF,
    0x8C, 0xA1, 0x89, 0x0D, 0xBF, 0xE6, 0x42, 0x68, 0x41, 0x99, 0x2D, 0x0F, 0xB0, 0x54, 0xBB, 0x16,
], dtype=np.uint8)

HW_LUT = np.array([bin(i).count("1") for i in range(256)], dtype=np.float64)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("results_dir", nargs="?", default="results/unmasked")
    ap.add_argument("--byte", type=int, default=0, dest="byte_idx",
                    help="Plaintext/key byte index to test (default: 0)")
    ap.add_argument("--plot", action="store_true", help="Generate rank plots")
    ap.add_argument("--out", default=None, help="Output prefix (default: <results_dir>/hw_model)")
    return ap.parse_args()


def load_csv_counter(path: Path) -> np.ndarray:
    vals = []
    with path.open(newline="") as f:
        r = csv.DictReader(f)
        if "hamming_weight_counter_t0" not in (r.fieldnames or []):
            raise ValueError(f"CSV missing hamming_weight_counter_t0: {path}")
        for row in r:
            vals.append(int(row["hamming_weight_counter_t0"]))
    if not vals:
        raise ValueError(f"CSV is empty: {path}")
    arr = np.array(vals, dtype=np.float64)
    d = np.empty_like(arr)
    d[0] = arr[0]
    d[1:] = arr[1:] - arr[:-1]
    return d


def load_manifest_plaintexts(manifest_path: Path, expected_n: int = 256) -> np.ndarray:
    data = json.loads(manifest_path.read_text())
    rows = data.get("scenarios", [])
    if len(rows) < expected_n:
        raise ValueError(f"Manifest has {len(rows)} scenarios, need {expected_n}: {manifest_path}")

    pts = np.zeros((expected_n, 16), dtype=np.uint8)
    for i in range(expected_n):
        entry = rows[i]
        bhex = entry.get("patched_labels", {}).get("aes_plaintext", {}).get("bytes_hex", "")
        blob = bytes.fromhex(bhex)
        if len(blob) != 16:
            raise ValueError(f"aes_plaintext length != 16 at index {i} in {manifest_path}")
        pts[i, :] = np.frombuffer(blob, dtype=np.uint8)
    return pts


def extract_key_bytes_from_scenario(script_dir: Path, scenario: str) -> np.ndarray:
    main_s = script_dir / "sw" / scenario / "main.S"
    if not main_s.is_file():
        raise FileNotFoundError(f"Cannot find scenario main.S for key extraction: {main_s}")

    lines = main_s.read_text().splitlines()
    for i, ln in enumerate(lines):
        if ln.strip().startswith("aes_key:"):
            key_bytes = []
            for j in range(i + 1, min(i + 8, len(lines))):
                s = lines[j].strip()
                if not s.startswith(".byte"):
                    continue
                toks = s.split(".byte", 1)[1].split(",")
                for t in toks:
                    t = t.strip().lower()
                    key_bytes.append(int(t, 16) if t.startswith("0x") else int(t, 10))
                if len(key_bytes) >= 16:
                    return np.array(key_bytes[:16], dtype=np.uint8)
            break

    raise ValueError(f"Could not parse aes_key bytes from {main_s}")


def pearson_vector_vs_matrix(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    xz = x - x.mean()
    yz = y - y.mean(axis=1, keepdims=True)
    x_den = np.linalg.norm(xz)
    y_den = np.linalg.norm(yz, axis=1)
    denom = x_den * y_den
    out = np.zeros(y.shape[0], dtype=np.float64)
    valid = denom > 0
    if np.any(valid):
        out[valid] = (yz[valid] @ xz) / denom[valid]
    return out


def run_group(
    results_dir: Path,
    prefix: str,
    plaintexts: np.ndarray,
    key_byte_truth: int,
    byte_idx: int,
) -> dict:
    traces = []
    for i in range(256):
        csv_path = results_dir / f"{prefix}_{i:03d}.csv"
        if not csv_path.is_file():
            raise FileNotFoundError(f"Missing required CSV: {csv_path}")
        traces.append(load_csv_counter(csv_path))

    x = np.vstack(traces)
    n_traces, n_cycles = x.shape

    pbyte = plaintexts[:, byte_idx].astype(np.uint8)
    model = np.zeros((256, n_traces), dtype=np.float64)
    for k in range(256):
        model[k, :] = HW_LUT[SBOX[np.bitwise_xor(pbyte, np.uint8(k))]]

    corr = np.zeros((256, n_cycles), dtype=np.float64)
    for c in range(n_cycles):
        corr[:, c] = pearson_vector_vs_matrix(x[:, c], model)

    abs_corr = np.abs(corr)
    max_per_key = abs_corr.max(axis=1)
    peak_cycle_per_key = abs_corr.argmax(axis=1)

    key_rank = int((max_per_key > max_per_key[key_byte_truth]).sum() + 1)
    key_peak_cycle = int(peak_cycle_per_key[key_byte_truth])
    key_peak_corr = float(corr[key_byte_truth, key_peak_cycle])

    best_key = int(np.argmax(max_per_key))
    best_cycle = int(peak_cycle_per_key[best_key])
    best_corr = float(corr[best_key, best_cycle])

    return {
        "corr": corr,
        "max_per_key": max_per_key,
        "peak_cycle_per_key": peak_cycle_per_key,
        "key_rank": key_rank,
        "key_peak_cycle": key_peak_cycle,
        "key_peak_corr": key_peak_corr,
        "best_key": best_key,
        "best_cycle": best_cycle,
        "best_corr": best_corr,
    }


def plot_rank(prefix: str, title: str, group_name: str, stats: dict, truth_key: int) -> None:
    if not HAS_MPL:
        return
    plt.figure(figsize=(10, 4))
    x = np.arange(256)
    y = stats["max_per_key"]
    plt.plot(x, y, color="steelblue", lw=1.2)
    plt.scatter([truth_key], [y[truth_key]], color="red", s=36, label=f"true key 0x{truth_key:02x}")
    plt.scatter([stats["best_key"]], [y[stats["best_key"]]], color="green", s=28, label=f"best key 0x{stats['best_key']:02x}")
    plt.title(f"{title} ({group_name})")
    plt.xlabel("Key hypothesis")
    plt.ylabel("max |corr| over cycles")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{prefix}_{group_name}_rank.png", dpi=140)
    plt.close()


def main() -> int:
    args = parse_args()
    results_dir = Path(args.results_dir).resolve()
    script_dir = Path(__file__).resolve().parent

    if args.byte_idx < 0 or args.byte_idx > 15:
        print("ERROR: --byte must be in [0, 15]", file=sys.stderr)
        return 1

    out_prefix = args.out or str(results_dir / "hw_model")

    manifest_a = script_dir / "sw" / "_manifests" / "multi_aes_unmasked_a_manifest.json"
    manifest_b = script_dir / "sw" / "_manifests" / "multi_aes_unmasked_b_manifest.json"
    if not manifest_a.is_file() or not manifest_b.is_file():
        print("ERROR: expected manifests not found in sw/_manifests for 256-case sweep", file=sys.stderr)
        return 1

    try:
        pt_a = load_manifest_plaintexts(manifest_a)
        pt_b = load_manifest_plaintexts(manifest_b)
        key_a = extract_key_bytes_from_scenario(script_dir, "scenario_aes128_key1")
        key_b = extract_key_bytes_from_scenario(script_dir, "scenario_aes128_key2")
    except Exception as e:
        print(f"ERROR: failed to load manifest/key data: {e}", file=sys.stderr)
        return 1

    if not np.array_equal(pt_a, pt_b):
        print("ERROR: group A/B manifests are not matched plaintext pairs", file=sys.stderr)
        return 1

    key_a_byte = int(key_a[args.byte_idx])
    key_b_byte = int(key_b[args.byte_idx])

    try:
        stats_a = run_group(results_dir, "group_a", pt_a, key_a_byte, args.byte_idx)
        stats_b = run_group(results_dir, "group_b", pt_b, key_b_byte, args.byte_idx)
    except Exception as e:
        print(f"ERROR: correlation run failed: {e}", file=sys.stderr)
        return 1

    print("=" * 70)
    print("HW-model correlation test")
    print(f"results_dir       : {results_dir}")
    print(f"byte index        : {args.byte_idx}")
    print(f"group A true key  : 0x{key_a_byte:02x}")
    print(f"group A key rank  : {stats_a['key_rank']}")
    print(f"group A peak cycle: {stats_a['key_peak_cycle']}")
    print(f"group A peak corr : {stats_a['key_peak_corr']:.5f}")
    print(f"group A best hyp  : 0x{stats_a['best_key']:02x} at cycle {stats_a['best_cycle']} (corr {stats_a['best_corr']:.5f})")
    print("-")
    print(f"group B true key  : 0x{key_b_byte:02x}")
    print(f"group B key rank  : {stats_b['key_rank']}")
    print(f"group B peak cycle: {stats_b['key_peak_cycle']}")
    print(f"group B peak corr : {stats_b['key_peak_corr']:.5f}")
    print(f"group B best hyp  : 0x{stats_b['best_key']:02x} at cycle {stats_b['best_cycle']} (corr {stats_b['best_corr']:.5f})")
    print("=" * 70)

    if args.plot:
        if not HAS_MPL:
            print("WARNING: matplotlib not available; skipping plots")
        else:
            plot_rank(out_prefix, f"AES HW-model correlation (byte {args.byte_idx})", "group_a", stats_a, key_a_byte)
            plot_rank(out_prefix, f"AES HW-model correlation (byte {args.byte_idx})", "group_b", stats_b, key_b_byte)
            print(f"Plots written: {out_prefix}_group_a_rank.png, {out_prefix}_group_b_rank.png")

    summary = {
        "results_dir": str(results_dir),
        "byte_index": int(args.byte_idx),
        "group_a": {
            "true_key_byte": key_a_byte,
            "key_rank": int(stats_a["key_rank"]),
            "peak_cycle": int(stats_a["key_peak_cycle"]),
            "peak_corr": float(stats_a["key_peak_corr"]),
            "best_key": int(stats_a["best_key"]),
            "best_cycle": int(stats_a["best_cycle"]),
            "best_corr": float(stats_a["best_corr"]),
        },
        "group_b": {
            "true_key_byte": key_b_byte,
            "key_rank": int(stats_b["key_rank"]),
            "peak_cycle": int(stats_b["key_peak_cycle"]),
            "peak_corr": float(stats_b["key_peak_corr"]),
            "best_key": int(stats_b["best_key"]),
            "best_cycle": int(stats_b["best_cycle"]),
            "best_corr": float(stats_b["best_corr"]),
        },
    }
    summary_path = Path(f"{out_prefix}_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"Summary written: {summary_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
