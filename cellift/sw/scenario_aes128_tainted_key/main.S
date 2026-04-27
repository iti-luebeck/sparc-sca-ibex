/*
 * AES-128 Tainted Key Scenario - Ibex Core
 * 
 * Main entry point and data definitions for the AES-128 test.
 * The key bytes are placed in a tainted section for CellIFT tracking.
 */

  .section ".text.init","ax",@progbits
  .globl _start
  .align 2

_start:
    /* Set up stack pointer */
    la sp, _stack_top

    /* 
     * Call AES-128 encryption
     * 
     * Arguments:
     *   a0 = pointer to AES context (for expanded keys)
     *   a1 = pointer to 16-byte key (TAINTED)
     *   a2 = pointer to 16-byte plaintext
     *   a3 = pointer to 16-byte ciphertext output
     */
    la a0, aes_context
    la a1, aes_key          /* THIS IS THE TAINT SOURCE */
    la a2, aes_plaintext
    la a3, aes_ciphertext
    
    /* Call the AES encryption function */
    call aes128_encrypt
    
    /* Done - infinite loop */
infinite_loop:
    j infinite_loop


/*
 * ============================================================================
 * DATA SECTION - Tainted Key
 * ============================================================================
 * The AES key is placed in a special .tainted_data section.
 * In CellIFT simulation, mark this memory region as tainted.
 */

  .section ".tainted_data","aw",@progbits
  .align 4

/*
 * AES-128 Secret Key (16 bytes) - TAINT SOURCE
 * 
 * This is the FIPS-197 Appendix B test vector key.
 * Mark these 16 bytes as tainted in CellIFT simulation.
 */
  .globl aes_key
aes_key:
    .byte 0x2b, 0x7e, 0x15, 0x16
    .byte 0x28, 0xae, 0xd2, 0xa6
    .byte 0xab, 0xf7, 0x15, 0x88
    .byte 0x09, 0xcf, 0x4f, 0x3c


/*
 * ============================================================================
 * DATA SECTION - Public Data (not tainted)
 * ============================================================================
 */

  .section ".data","aw",@progbits
  .align 4

/*
 * Plaintext input block (16 bytes) - NOT tainted
 * FIPS-197 Appendix B test vector
 */
  .globl aes_plaintext
aes_plaintext:
    .byte 0x32, 0x43, 0xf6, 0xa8
    .byte 0x88, 0x5a, 0x30, 0x8d
    .byte 0x31, 0x31, 0x98, 0xa2
    .byte 0xe0, 0x37, 0x07, 0x34

/*
 * Ciphertext output block (16 bytes)
 * Will become tainted after encryption.
 * Expected result: 0x3925841d02dc09fbdc118597196a0b32
 */
  .globl aes_ciphertext
aes_ciphertext:
    .space 16, 0x00

/*
 * AES context / expanded key schedule (176 bytes)
 * Will become tainted during key expansion.
 */
  .globl aes_context
aes_context:
    .space 176, 0x00
