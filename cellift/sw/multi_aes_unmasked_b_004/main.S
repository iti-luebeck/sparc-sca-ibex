/*
 * AES-128 Test Scenario - KEY 2
 * 
 * This variant uses a different test key for TVLA analysis.
 * Different from key1 to allow leakage comparison.
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
    la a1, aes_key          /* THIS IS THE TAINT SOURCE - KEY 2 */
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
 * KEY 2: Different from KEY 1 to observe leakage differences
 * This is a complementary test vector.
 */
  .globl aes_key
aes_key:
    .byte 0xff, 0xfe, 0xfd, 0xfc
    .byte 0xfb, 0xfa, 0xf9, 0xf8
    .byte 0xf7, 0xf6, 0xf5, 0xf4
    .byte 0xf3, 0xf2, 0xf1, 0xf0


/*
 * ============================================================================
 * DATA SECTION - Public Data (not tainted)
 * ============================================================================
 */

  .section ".data","aw",@progbits
  .align 4

/*
 * Plaintext input block (16 bytes) - NOT tainted
 * Same for both KEY1 and KEY2 to isolate key differences
 */
  .globl aes_plaintext
aes_plaintext:
    .byte 0xff, 0xa1, 0xa0, 0x83
    .byte 0xad, 0xa6, 0x9b, 0x7a
    .byte 0xbb, 0x64, 0x2c, 0x80
    .byte 0x26, 0x79, 0xc7, 0x1d

/*
 * Ciphertext output buffer (16 bytes)
 */
  .globl aes_ciphertext
aes_ciphertext:
    .zero 16

/*
 * AES context buffer for expanded keys (176 bytes)
 * This will be populated during key expansion
 */
  .globl aes_context
aes_context:
    .zero 176

/*
 * Stack space (at end of memory)
 */
  .section ".stack","aw",@nobits
  .align 4
  .space 1024
  .globl _stack_top
_stack_top:
