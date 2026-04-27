/*
 * AES-128 Test Scenario - KEY 1
 * 
 * This variant uses a specific test key for TVLA analysis.
 * Different from key2 to allow leakage comparison.
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
    la a1, aes_key          /* THIS IS THE TAINT SOURCE - KEY 1 */
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
 * KEY 1: Different from KEY 2 to observe leakage differences
 * This is a reference test vector.
 */
  .globl aes_key
aes_key:
    .byte 0x00, 0x01, 0x02, 0x03
    .byte 0x04, 0x05, 0x06, 0x07
    .byte 0x08, 0x09, 0x0a, 0x0b
    .byte 0x0c, 0x0d, 0x0e, 0x0f


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
    .byte 0x76, 0x18, 0x2c, 0x24
    .byte 0x3f, 0x5f, 0x73, 0x99
    .byte 0x1d, 0x8c, 0x53, 0x63
    .byte 0x13, 0x8b, 0x68, 0x64

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
