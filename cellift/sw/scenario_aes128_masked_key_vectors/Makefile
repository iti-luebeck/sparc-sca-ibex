RISCV_PREFIX = riscv64-unknown-elf

# Ibex is RV32IMC
RV_ARCH_FLAGS ?= -march=rv32imc -mabi=ilp32
RISCV_GCC_OPTS ?= $(RV_ARCH_FLAGS) -DPREALLOCATE=1 -mcmodel=medany -static -std=gnu99 -O2 -ffast-math -fno-common -fno-builtin-printf -fno-tree-loop-distribute-patterns -gdwarf-2
LDFLAGS = -Tlink.ld -static -nostdlib -nostartfiles -lm -lgcc
RISCV_OBJDUMP ?= $(RISCV_PREFIX)-objdump -d

CC = $(RISCV_PREFIX)-gcc
PYTHON ?= python3

SRCS = main.S main.c aes128_masked.c
VECTORS_DIR = test_patterns
MANIFEST = $(VECTORS_DIR)/manifest.txt

VECTORS := $(shell if [ -f $(MANIFEST) ]; then cat $(MANIFEST); else ls $(VECTORS_DIR)/vector_*.h 2>/dev/null; fi)
VECTOR_IDS := $(patsubst vector_%.h,%,$(notdir $(VECTORS)))
BINARIES := $(addprefix build/app_,$(addsuffix .elf,$(VECTOR_IDS)))

all: $(BINARIES)

build/app_%.elf: $(SRCS) link.ld $(VECTORS_DIR)/vector_%.h | build
	$(CC) $(RISCV_GCC_OPTS) $(SRCS) -o $@ $(LDFLAGS) -DVECTOR_HEADER=\"$(VECTORS_DIR)/vector_$*.h\"
	$(RISCV_OBJDUMP) $@ > $@.dump

build:
	mkdir -p build

.PHONY: generate_vectors
# Example: make generate_vectors COUNT=10 RANDOM_KEY=1 SEED=1234
#          make generate_vectors COUNT=5 FIXED_KEY=2b7e151628aed2a6abf7158809cf4f3c

generate_vectors:
	$(PYTHON) scripts/generate_test_vectors.py \
		--out-dir $(VECTORS_DIR) \
		--count $${COUNT:-1} \
		$${SEED:+--seed $${SEED}} \
		$${FIXED_KEY:+--fixed-key $${FIXED_KEY}} \
		$${RANDOM_KEY:+--random-key}

.PHONY: clean clean_vectors
clean:
	rm -rf build

clean_vectors:
	rm -rf $(VECTORS_DIR)/vector_*.h $(MANIFEST)
