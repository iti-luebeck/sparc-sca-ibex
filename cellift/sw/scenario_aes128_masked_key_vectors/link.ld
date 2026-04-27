OUTPUT_ARCH( "riscv" )
ENTRY(_start)

SECTIONS
{
  . = 0x00000080;
  .text.init : { *(.text.init) }
  . = ALIGN(0x100);
  .text : { *(.text) }
  . = ALIGN(0x100);
  .rodata : { *(.rodata*) }
  . = ALIGN(0x100);
  .data : { *(.data*) }
  . = ALIGN(0x100);
  .bss : { *(.bss*) }
  . = ALIGN(0x100);

  /* Stack */
  . += 0x400;
  _stack_top = .;

  /* Tainted data section - key share lives here */
  . = 0x00000C00;
  .tainted_data : { *(.tainted_data) }
  tainted_region_start = ADDR(.tainted_data);
  tainted_region_end = ADDR(.tainted_data) + SIZEOF(.tainted_data);
}
