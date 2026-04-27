RISCV_PREFIX = riscv64-unknown-elf

# Ibex is RV32IMC
RV_ARCH_FLAGS ?= -march=rv32imc -mabi=ilp32
RISCV_GCC_OPTS ?= $(RV_ARCH_FLAGS) -DPREALLOCATE=1 -mcmodel=medany -static -std=gnu99 -O2 -ffast-math -fno-common -fno-builtin-printf -fno-tree-loop-distribute-patterns -gdwarf-2
LDFLAGS = -Tlink.ld -static -nostdlib -nostartfiles -lm -lgcc
RISCV_OBJDUMP ?= $(RISCV_PREFIX)-objdump -d

CC = $(RISCV_PREFIX)-gcc

SRCS = main.S tinyai.c

build/app.elf: $(SRCS) link.ld | build
	$(CC) $(RISCV_GCC_OPTS) $(SRCS) -o $@ $(LDFLAGS)
	$(RISCV_OBJDUMP) $@ > $@.dump
	@echo ""
	@echo "=== Build complete ==="
	@echo "Binary: $@"
	@$(RISCV_PREFIX)-size $@
	@echo ""
	@echo "Tainted data section (3x3 weight matrix, 9 bytes):"
	@$(RISCV_PREFIX)-objdump -h $@ | grep tainted || true
	@echo ""
	@echo "Next: Update taint_data.txt with the .tainted_data address"

build:
	mkdir -p build

.PHONY: clean
clean:
	rm -rf build input_*.h

.PHONY: show-sections
show-sections: build/app.elf
	$(RISCV_PREFIX)-objdump -h $<

.PHONY: show-symbols
show-symbols: build/app.elf
	$(RISCV_PREFIX)-nm $< | grep -E "weights|input|output"

.PHONY: show-weights
show-weights: build/app.elf
	@echo "Weight matrix (3x3 uint8_t):"
	@$(RISCV_PREFIX)-objdump -s -j .tainted_data $< | tail -n +5
