# Automated Root-Cause Analysis Report

## Run Configuration

- workload: kyber
- seed: 42
- simlen: 2000000
- threshold_t: 4.5
- interval_top_k: 8

## Unmasked Attribution Summary

- first_hw_leak_cycle: 18351
- intervals analyzed: 16
- intervals with both signal+instruction: 0 (0.00%)

| Counter | Basis | Regime | Interval | Peak cycle | Peak mag | Peak d | Peak t | Signal | Top signals (HW diff) | Instruction | Source |
|---|---|---|---|---:|---:|---:|---:|---|---|---|---|
| hamming_weight_counter_t0 | episode | det_leak | 22111-22129 | 22115 | 67.0 | 1000.0 | n/a | n/a | n/a | sh a5,0(a0) | pqcrystals_kyber512_ref_poly_frombytes /mnt/nvme1n1p1/cellift-designs/cellift-ibex/cellift/sw/scenario_kyber_unmasked_key1/poly.c:134 (di... |
| hamming_weight_counter_t0 | episode | det_leak | 21107-21125 | 21111 | 64.0 | 1000.0 | n/a | n/a | n/a | addi a1,a1,3 | pqcrystals_kyber512_ref_poly_frombytes /mnt/nvme1n1p1/cellift-designs/cellift-ibex/cellift/sw/scenario_kyber_unmasked_key1/poly.c:133 (di... |
| hamming_weight_counter_t0 | episode | det_leak | 19781-19799 | 19797 | 61.0 | 1000.0 | n/a | n/a | n/a | addi a1,a1,3 | pqcrystals_kyber512_ref_poly_frombytes /mnt/nvme1n1p1/cellift-designs/cellift-ibex/cellift/sw/scenario_kyber_unmasked_key1/poly.c:133 (di... |
| hamming_weight_counter_t0 | episode | det_leak | 20327-20345 | 20343 | 60.0 | 1000.0 | n/a | n/a | n/a | addi a1,a1,3 | pqcrystals_kyber512_ref_poly_frombytes /mnt/nvme1n1p1/cellift-designs/cellift-ibex/cellift/sw/scenario_kyber_unmasked_key1/poly.c:133 (di... |
| hamming_weight_counter_t0 | episode | det_leak | 20821-20839 | 20836 | 60.0 | 1000.0 | n/a | n/a | n/a | addi a1,a1,3 | pqcrystals_kyber512_ref_poly_frombytes /mnt/nvme1n1p1/cellift-designs/cellift-ibex/cellift/sw/scenario_kyber_unmasked_key1/poly.c:133 (di... |
| hamming_weight_counter_t0 | episode | det_leak | 20119-20137 | 20135 | 59.0 | 1000.0 | n/a | n/a | n/a | addi a1,a1,3 | pqcrystals_kyber512_ref_poly_frombytes /mnt/nvme1n1p1/cellift-designs/cellift-ibex/cellift/sw/scenario_kyber_unmasked_key1/poly.c:133 (di... |
| hamming_weight_counter_t0 | episode | det_leak | 21159-21177 | 21175 | 55.0 | 1000.0 | n/a | n/a | n/a | addi a1,a1,3 | pqcrystals_kyber512_ref_poly_frombytes /mnt/nvme1n1p1/cellift-designs/cellift-ibex/cellift/sw/scenario_kyber_unmasked_key1/poly.c:133 (di... |
| hamming_weight_counter_t0 | episode | det_leak | 20067-20085 | 20083 | 54.0 | 1000.0 | n/a | n/a | n/a | addi a1,a1,3 | pqcrystals_kyber512_ref_poly_frombytes /mnt/nvme1n1p1/cellift-designs/cellift-ibex/cellift/sw/scenario_kyber_unmasked_key1/poly.c:133 (di... |
| hamming_distance_counter_t0 | episode | det_leak | 18923-18940 | 18927 | 46.0 | 1000.0 | n/a | n/a | n/a | addi a1,a1,3 | pqcrystals_kyber512_ref_poly_frombytes /mnt/nvme1n1p1/cellift-designs/cellift-ibex/cellift/sw/scenario_kyber_unmasked_key1/poly.c:133 (di... |
| hamming_distance_counter_t0 | episode | det_leak | 20587-20604 | 20591 | 43.0 | 1000.0 | n/a | n/a | n/a | addi a1,a1,3 | pqcrystals_kyber512_ref_poly_frombytes /mnt/nvme1n1p1/cellift-designs/cellift-ibex/cellift/sw/scenario_kyber_unmasked_key1/poly.c:133 (di... |
| hamming_distance_counter_t0 | episode | det_leak | 20119-20136 | 20134 | 41.0 | 1000.0 | n/a | n/a | n/a | addi a1,a1,3 | pqcrystals_kyber512_ref_poly_frombytes /mnt/nvme1n1p1/cellift-designs/cellift-ibex/cellift/sw/scenario_kyber_unmasked_key1/poly.c:133 (di... |
| hamming_distance_counter_t0 | episode | det_leak | 21159-21176 | 21174 | 41.0 | 1000.0 | n/a | n/a | n/a | addi a1,a1,3 | pqcrystals_kyber512_ref_poly_frombytes /mnt/nvme1n1p1/cellift-designs/cellift-ibex/cellift/sw/scenario_kyber_unmasked_key1/poly.c:133 (di... |
| hamming_distance_counter_t0 | episode | det_leak | 18351-18368 | 18355 | 39.0 | 1000.0 | n/a | n/a | n/a | n/a | n/a |
| hamming_distance_counter_t0 | episode | det_leak | 20431-20448 | 20435 | 36.0 | 1000.0 | n/a | n/a | n/a | n/a | n/a |
| hamming_distance_counter_t0 | episode | det_leak | 20535-20552 | 20539 | 36.0 | 1000.0 | n/a | n/a | n/a | n/a | n/a |
| hamming_distance_counter_t0 | episode | det_leak | 20821-20838 | 20836 | 36.0 | 1000.0 | n/a | n/a | n/a | addi a1,a1,3 | pqcrystals_kyber512_ref_poly_frombytes /mnt/nvme1n1p1/cellift-designs/cellift-ibex/cellift/sw/scenario_kyber_unmasked_key1/poly.c:133 (di... |

## Efficacy Evidence

- Leakage regions are auto-extracted from TVLA outputs using two definitions (episode and strict Welch).
- Region-level root-cause attribution is automatic and links hardware signals with software instructions.
- Coverage ratios quantify how often intervals have complete signal+instruction attribution.
