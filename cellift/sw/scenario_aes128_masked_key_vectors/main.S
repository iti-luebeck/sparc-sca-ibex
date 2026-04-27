/*
 * AES-128 Masked Key Vector Scenario - Ibex Core
 *
 * Minimal entry point that calls c_main() and loops forever.
 */

  .section ".text.init","ax",@progbits
  .globl _start
  .align 2

_start:
    /* Set up stack pointer */
    la sp, _stack_top

    /* Call C entry */
    call c_main

infinite_loop:
    j infinite_loop
