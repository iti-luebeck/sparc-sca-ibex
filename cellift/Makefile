# Copyright 2022 Flavien Solt, ETH Zurich.
# Copyright (C) 2024-2026 Andrija Neskovic, University of Luebeck
# Licensed under the General Public License, Version 3.0, see LICENSE for details.
# SPDX-License-Identifier: GPL-3.0-only

ifeq "" "$(CELLIFT_ENV_SOURCED)"
$(error Please re-source env.sh first, in the meta repo, and run from there, not this repo. See README.md in the meta repo)
endif

CURR_OPENTITAN_ROOT = $(OPENTITAN_ROOT)

ifeq "" "$(CURR_OPENTITAN_ROOT)"
$(error OPENTITAN_ROOT is not set. Source env.sh or export OPENTITAN_ROOT before running make.)
endif

# Paths used by the evaluation simulator build rules.
IBEX_CORES_ROOT   = ..
OPENTITAN_HW_ROOT = $(OPENTITAN_ROOT)/hw

#
# 0. Install the Python requirements
#
installrequirements:
	$(CELLIFT_PYTHON_VENV)/bin/pip install -r ../python-requirements.txt

PYTHON ?= python3
RESOURCEWRAPPER_TAG ?= ibex

TOP_MODULE = cellift_rv_core_ibex_mem_top
TOP_EXECUTABLE_NAME = Vibex_tiny_soc

# The `passthrough` target is useful so that the log matches with the sv on the generated block names, typically for ideal taint experiments.
TARGET_NAMES = vanilla cellift glift passthrough

include $(CELLIFT_DESIGN_PROCESSING_ROOT)/common/design.mk

# This target makes the design until the Yosys instrumentation. From there on, the Makefile can run in parallel for the various instrumentation targets.
before_instrumentation: generated/sv2v_out.v

#
# 1. Gather the source code.
#

generated/scattered/rv_core_ibex.v: | generated/sv_sources generated/scattered
	rm -f fusesoc.conf
	fusesoc library add ibex_cellift ..
	fusesoc --cores-root=$(CURR_OPENTITAN_ROOT) run --build --target=synth ibex_cellift
	rm -rf generated/sv_sources/*
	find build/ibex_cellift_0.1 -name \*.sv  -exec cp {} generated/sv_sources \;
	find build/ibex_cellift_0.1 -name \*.svh -exec cp {} generated/sv_sources \;

#
# 2. Pickle the source code & apply sv2v.
#

generated/noprefix.v: generated/scattered/rv_core_ibex.v | generated
	rm -f generated/scattered/*.v
	$(PYTHON) scripts/gen_sv2v_out.py
	cat generated/scattered/*.v > $@

# Add the cellift_ prefix everywhere.
generated/out/vanilla.sv: generated/noprefix.v | generated/out
# 	Add prefixes to module names.
	morty $< -p cellift_ > $@
# 	Replace occurrences of wor
	sed -i 's/\bwor\b/logic/g' $@

generated/out/vanilla.sv.log: | generated/out
	touch $@

.PHONY: sv2v_singlefile
sv2v_singlefile: generated/sv2v_out.v
generated/sv2v_out.v: generated/out/vanilla.sv | generated
	sv2v -D SYNTHESIS -Igenerated/sv_sources $< -w $@
# 	Replace occurrences of wor
	sed -i 's/\bwor\b/logic/g' $@
# Add newline in the end of the file because sv2v does not.
	echo  >> $@


generated/out/nosv2v.sv: generated/scattered/rv_core_ibex.v | generated/out
	find generated/sv_sources -type f -name "*.sv" -exec cat {} + > $@

#
# 3. Instrument using Yosys.
#

YOSYS_INSTRUMENTATION_TARGETS_SV=$(patsubst %,generated/out/%.sv, cellift glift passthrough)

$(YOSYS_INSTRUMENTATION_TARGETS_SV): generated/out/%.sv: $(CELLIFT_YS)/instrument.ys.tcl generated/sv2v_out.v | generated/out logs
	DECOMPOSE_MEMORY=1 VERILOG_INPUT=$(word 2,$^) INSTRUMENTATION=$* VERILOG_OUTPUT=$@ TOP_MODULE=$(TOP_MODULE) $(CELLIFT_META_ROOT)/resourcewrapper $(RESOURCEWRAPPER_TAG) $* instr yosys -c $< -l $@.log

# CellIFT without power-leakage counters (for HD/HW overhead benchmarking).
generated/out/cellift_taint_only.sv: $(CELLIFT_YS)/instrument.ys.tcl generated/sv2v_out.v | generated/out logs
	DECOMPOSE_MEMORY=1 VERILOG_INPUT=$(word 2,$^) INSTRUMENTATION=cellift TRACK_POWER_LEAKAGE=0 VERILOG_OUTPUT=$@ TOP_MODULE=$(TOP_MODULE) $(CELLIFT_META_ROOT)/resourcewrapper $(RESOURCEWRAPPER_TAG) cellift_taint_only instr yosys -c $< -l $@.log

generated/out/cellift_taint_only.sv.log: | generated/out
	touch $@
#
# Verilator simulation
#

# Phony targets

PREPARE_TARGETS_NOTRACE=$(patsubst %,prepare_%_notrace, $(TARGET_NAMES))
PREPARE_TARGETS_TRACE=$(patsubst %,prepare_%_trace, $(TARGET_NAMES))
PREPARE_TARGETS_TRACE_FST=$(patsubst %,prepare_%_trace_fst, $(TARGET_NAMES))
PREPARE_TARGETS = $(PREPARE_TARGETS_NOTRACE) $(PREPARE_TARGETS_TRACE) $(PREPARE_TARGETS_TRACE_FST)

.PHONY: $(PREPARE_TARGETS)
$(PREPARE_TARGETS): prepare_%: build/run_%_0.1/default-verilator/$(TOP_EXECUTABLE_NAME)

# Actual targets

BUILD_TARGETS_NOTRACE=$(patsubst %,build/run_%_notrace_0.1/default-verilator/$(TOP_EXECUTABLE_NAME), $(TARGET_NAMES))
BUILD_TARGETS_TRACE=$(patsubst %,build/run_%_trace_0.1/default-verilator/$(TOP_EXECUTABLE_NAME), $(TARGET_NAMES))
BUILD_TARGETS_TRACE_FST=$(patsubst %,build/run_%_trace_fst_0.1/default-verilator/$(TOP_EXECUTABLE_NAME), $(TARGET_NAMES))
BUILD_TARGETS = $(BUILD_TARGETS_NOTRACE) $(BUILD_TARGETS_TRACE) $(BUILD_TARGETS_TRACE_FST)

$(BUILD_TARGETS_NOTRACE): build/run_%_notrace_0.1/default-verilator/$(TOP_EXECUTABLE_NAME): generated/out/%.sv generated/out/%.sv.log
	rm -f fusesoc.conf
	fusesoc library add run_$*_notrace .
	$(CELLIFT_META_ROOT)/resourcewrapper $(RESOURCEWRAPPER_TAG) $*_notrace synth fusesoc --cores-root=$(CURR_OPENTITAN_ROOT) run --build run_$*_notrace
	cp $<.log $@.log
$(BUILD_TARGETS_TRACE): build/run_%_trace_0.1/default-verilator/$(TOP_EXECUTABLE_NAME): generated/out/%.sv generated/out/%.sv.log
	rm -f fusesoc.conf
	fusesoc library add run_$*_trace .
	$(CELLIFT_META_ROOT)/resourcewrapper $(RESOURCEWRAPPER_TAG) $*_trace synth fusesoc --cores-root=$(CURR_OPENTITAN_ROOT) run --build run_$*_trace
	cp $<.log $@.log
$(BUILD_TARGETS_TRACE_FST): build/run_%_trace_fst_0.1/default-verilator/$(TOP_EXECUTABLE_NAME): generated/out/%.sv generated/out/%.sv.log
	rm -f fusesoc.conf
	fusesoc library add run_$*_trace_fst .
	$(CELLIFT_META_ROOT)/resourcewrapper $(RESOURCEWRAPPER_TAG) $*_trace_fst synth fusesoc --cores-root=$(CURR_OPENTITAN_ROOT) run --build run_$*_trace_fst
	cp $<.log $@.log

#
# Recompile, if only the Verilator C++ testbench has changed
#

RECOMPILE_TARGETS_NOTRACE=$(patsubst %,recompile_%_notrace, $(TARGET_NAMES))
RECOMPILE_TARGETS_TRACE=$(patsubst %,recompile_%_trace, $(TARGET_NAMES))
RECOMPILE_TARGETS_TRACE_FST=$(patsubst %,recompile_%_trace_fst, $(TARGET_NAMES))
RECOMPILE_TARGETS = $(RECOMPILE_TARGETS_NOTRACE) $(RECOMPILE_TARGETS_TRACE) $(RECOMPILE_TARGETS_TRACE_FST)

.PHONY: $(RECOMPILE_TARGETS)
$(RECOMPILE_TARGETS): recompile_%: build/run_%_0.1
	rm -f $</default-verilator/toplevel.o
	rm -f $</default-verilator/$(TOP_EXECUTABLE_NAME)
	rm -rf $</src/run_$*_0.1/dv
	rm -rf ./build/dv
	cp -r dv $</src/run_$*_0.1
	cp -r $(CELLIFT_DESIGN_PROCESSING_ROOT)/common/dv ./build
	make -C $</default-verilator


#
# Rerun, while making sure that nothing will be recompiled because of this call.
#

RERUN_TARGETS_NOTRACE=$(patsubst %,rerun_%_notrace, $(TARGET_NAMES))
RERUN_TARGETS_TRACE=$(patsubst %,rerun_%_trace, $(TARGET_NAMES))
RERUN_TARGETS_TRACE_FST=$(patsubst %,rerun_%_trace_fst, $(TARGET_NAMES))
RERUN_TARGETS = $(RERUN_TARGETS_NOTRACE) $(RERUN_TARGETS_TRACE) $(RERUN_TARGETS_TRACE_FST)

.PHONY: $(RERUN_TARGETS)
$(RERUN_TARGETS_TRACE) $(RERUN_TARGETS_TRACE_FST): | traces
$(RERUN_TARGETS): rerun_%: build/run_%_0.1/
	$</default-verilator/$(TOP_EXECUTABLE_NAME)

#
# Run, potentially after compiling.
#

RUN_TARGETS_NOTRACE=$(patsubst %,run_%_notrace, $(TARGET_NAMES))
RUN_TARGETS_TRACE=$(patsubst %,run_%_trace, $(TARGET_NAMES))
RUN_TARGETS_TRACE_FST=$(patsubst %,run_%_trace_fst, $(TARGET_NAMES))
RUN_TARGETS = $(RUN_TARGETS_NOTRACE) $(RUN_TARGETS_TRACE) $(RUN_TARGETS_TRACE_FST)

$(RUN_TARGETS_TRACE) $(RUN_TARGETS_TRACE_FST): | traces
$(RUN_TARGETS): run_%: ./build/run_%_0.1/default-verilator/$(TOP_EXECUTABLE_NAME)
	cd build/run_$*_0.1/default-verilator && $(CELLIFT_META_ROOT)/resourcewrapper $(RESOURCEWRAPPER_TAG) $* run ./$(TOP_EXECUTABLE_NAME)

#
# Extract Yosys cell statistics
#

STATISTICS_TARGETS=$(patsubst %,statistics/%.log, $(TARGET_NAMES))

$(STATISTICS_TARGETS): statistics/%.log: $(CELLIFT_YS)/statistics.ys.tcl generated/sv2v_out.v | statistics
	DECOMPOSE_MEMORY=1 VERILOG_INPUT=$(word 2,$^) INSTRUMENTATION=$* TOP_MODULE=$(TOP_MODULE) $(CELLIFT_META_ROOT)/resourcewrapper $(RESOURCEWRAPPER_TAG) $* stat yosys -c $< -l $@

# ── Evaluation simulators ─────────────────────────────────────────────────────
# Copyright (C) 2024-2026 Andrija Neskovic, University of Luebeck
#
# These four simulators are the ones required by run_full_evaluation.sh and
# run_full_audit.sh.  The targets depend on the instrumented RTL, which is built
# by the Yosys pass above (generated/out/cellift.sv, generated/out/vanilla.sv).
# Running `make build-eval-sims` therefore triggers the full chain from RTL
# preprocessing through Yosys instrumentation to Verilator compilation.

EVAL_SIM_CSVLOG      = build/run_cellift_csvlog_0.1/default-verilator/$(TOP_EXECUTABLE_NAME)
EVAL_SIM_FASTTRACE   = build/run_cellift_fasttrace_0.1/default-verilator/$(TOP_EXECUTABLE_NAME)
EVAL_SIM_VANILLA     = build/run_vanilla_trace_0.1/default-verilator/$(TOP_EXECUTABLE_NAME)
EVAL_SIM_VANILLA_FST = build/run_vanilla_trace_fst_0.1/default-verilator/$(TOP_EXECUTABLE_NAME)

.PHONY: build-eval-sims
build-eval-sims: $(EVAL_SIM_CSVLOG) $(EVAL_SIM_FASTTRACE) $(EVAL_SIM_VANILLA) $(EVAL_SIM_VANILLA_FST)

$(EVAL_SIM_CSVLOG): generated/out/cellift.sv generated/out/cellift.sv.log | logs
	rm -f fusesoc.conf
	fusesoc library add run_cellift_csvlog .
	fusesoc --cores-root=. --cores-root=$(IBEX_CORES_ROOT) \
	    --cores-root=$(OPENTITAN_HW_ROOT) run --build run_cellift_csvlog

$(EVAL_SIM_FASTTRACE): generated/out/cellift.sv generated/out/cellift.sv.log | logs
	rm -f fusesoc.conf
	fusesoc library add run_cellift_fasttrace .
	fusesoc --cores-root=. --cores-root=$(IBEX_CORES_ROOT) \
	    --cores-root=$(OPENTITAN_HW_ROOT) run --build run_cellift_fasttrace

$(EVAL_SIM_VANILLA): generated/out/vanilla.sv generated/out/vanilla.sv.log | logs
	rm -f fusesoc.conf
	fusesoc library add run_vanilla_trace .
	fusesoc --cores-root=. --cores-root=$(IBEX_CORES_ROOT) \
	    --cores-root=$(OPENTITAN_HW_ROOT) run --build run_vanilla_trace

$(EVAL_SIM_VANILLA_FST): generated/out/vanilla.sv generated/out/vanilla.sv.log | logs
	rm -f fusesoc.conf
	fusesoc library add run_vanilla_trace_fst .
	fusesoc --cores-root=. --cores-root=$(IBEX_CORES_ROOT) \
	    --cores-root=$(OPENTITAN_HW_ROOT) run --build run_vanilla_trace_fst

# ── Benchmark simulators ──────────────────────────────────────────────────────
# Three variants with matching -O2 optimisation and no --trace flag, so that
# timing differences reflect instrumentation overhead alone:
#   vanilla_bench     — unmodified Ibex (true baseline)
#   cellift_bench_nocsv — CellIFT instrumented, no output (pure RTL overhead)
#   cellift_bench_csv   — CellIFT instrumented, CSV per-cycle (full HD/HW pipeline)

BENCH_SIM_VANILLA    = build/run_vanilla_bench_0.1/default-verilator/$(TOP_EXECUTABLE_NAME)
BENCH_SIM_TAINT_ONLY = build/run_cellift_bench_taint_only_0.1/default-verilator/$(TOP_EXECUTABLE_NAME)
BENCH_SIM_NOCSV      = build/run_cellift_bench_nocsv_0.1/default-verilator/$(TOP_EXECUTABLE_NAME)
BENCH_SIM_CSV        = build/run_cellift_bench_csv_0.1/default-verilator/$(TOP_EXECUTABLE_NAME)

.PHONY: build-bench-sims
build-bench-sims: $(BENCH_SIM_VANILLA) $(BENCH_SIM_TAINT_ONLY) $(BENCH_SIM_NOCSV) $(BENCH_SIM_CSV)

$(BENCH_SIM_VANILLA): generated/out/vanilla.sv generated/out/vanilla.sv.log | logs
	rm -f fusesoc.conf
	fusesoc library add run_vanilla_bench .
	fusesoc --cores-root=. --cores-root=$(IBEX_CORES_ROOT) \
	    --cores-root=$(OPENTITAN_HW_ROOT) run --build run_vanilla_bench

$(BENCH_SIM_TAINT_ONLY): generated/out/cellift_taint_only.sv generated/out/cellift_taint_only.sv.log | logs
	rm -f fusesoc.conf
	fusesoc library add run_cellift_bench_taint_only .
	fusesoc --cores-root=. --cores-root=$(IBEX_CORES_ROOT) \
	    --cores-root=$(OPENTITAN_HW_ROOT) run --build run_cellift_bench_taint_only

$(BENCH_SIM_NOCSV): generated/out/cellift.sv generated/out/cellift.sv.log | logs
	rm -f fusesoc.conf
	fusesoc library add run_cellift_bench_nocsv .
	fusesoc --cores-root=. --cores-root=$(IBEX_CORES_ROOT) \
	    --cores-root=$(OPENTITAN_HW_ROOT) run --build run_cellift_bench_nocsv

$(BENCH_SIM_CSV): generated/out/cellift.sv generated/out/cellift.sv.log | logs
	rm -f fusesoc.conf
	fusesoc library add run_cellift_bench_csv .
	fusesoc --cores-root=. --cores-root=$(IBEX_CORES_ROOT) \
	    --cores-root=$(OPENTITAN_HW_ROOT) run --build run_cellift_bench_csv
