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
  
  /* Tainted data section - AES key lives here at 0xC00 */
  . = 0x00000C00;
  .tainted_data : { *(.tainted_data) }
  tainted_region_start = ADDR(.tainted_data);
  tainted_region_end = ADDR(.tainted_data) + SIZEOF(.tainted_data);
}
