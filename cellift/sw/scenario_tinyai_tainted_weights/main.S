/*
 * Simple 3x3 Matrix-Vector Multiplication - Ibex Core
 * 
 * Main entry point for a minimal matrix multiplication example.
 * The weight matrix is placed in a tainted section for CellIFT tracking.
 * 
 * Computes: output = weights * input (3x3 matrix times 3x1 vector)
 * 
 * Uses 8-bit unsigned integers for power side-channel analysis.
 */

  .section ".text.init","ax",@progbits
  .globl _start
  .align 2

_start:
    /* Set up stack pointer */
    la sp, _stack_top

    /* 
     * Run matrix-vector multiplication
     * 
     * Arguments:
     *   a0 = pointer to input vector (3 x uint8_t)
     *   a1 = pointer to weights (3x3 = 9 x uint8_t) - TAINTED
     *   a2 = pointer to output vector (3 x uint16_t)
     */
    la a0, input_vec
    la a1, weights       /* TAINT SOURCE - weight matrix */
    la a2, output_vec
    
    /* Call the multiplication function */
    call mat_vec_mul
    
    /* Done - infinite loop */
infinite_loop:
    j infinite_loop


/*
 * ============================================================================
 * TAINTED DATA SECTION - Weight Matrix
 * ============================================================================
 * The 3x3 weight matrix is placed in .tainted_data section.
 * In CellIFT simulation, mark this memory region as tainted.
 * 
 * Uses 8-bit unsigned integers (0-255) for simple power analysis.
 */

  .section ".tainted_data","aw",@progbits
  .align 4

/*
 * Weight matrix: 3x3 = 9 bytes
 * Stored row-major: weights[row][col] = weights[row * 3 + col]
 */
  .globl weights
weights:
    .byte  10,  20,  30    /* Row 0 */
    .byte  40,  50,  60    /* Row 1 */
    .byte  70,  80,  90    /* Row 2 */


/*
 * ============================================================================
 * PUBLIC DATA SECTION - Not tainted
 * ============================================================================
 */

  .section ".data","aw",@progbits
  .align 4

/*
 * Input vector: 3 elements (uint8_t)
 */
  .globl input_vec
input_vec:
    .byte  1,  2,  3

  .align 4

/*
 * Output vector: 3 elements (uint16_t, to hold accumulation results)
 * Will become tainted after multiplication.
 */
  .globl output_vec
output_vec:
    .space 6, 0x00
