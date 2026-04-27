/*
 * AES-128 Masked Key Scenario - Ibex Core
 *
 * Main entry point and data definitions for the masked AES-128 test.
 * The masked key share is placed in a tainted section for CellIFT tracking.
 */

  .section ".text.init","ax",@progbits
  .globl _start
  .align 2

_start:
    /* Set up stack pointer */
    la sp, _stack_top

    /*
     * Call masked AES-128 encryption
     *
     * Arguments:
     *   a0 = pointer to AES context (expanded keys)
     *   a1 = pointer to key_share0 (TAINTED)
     *   a2 = pointer to key_mask (NOT tainted)
     *   a3 = pointer to 16-byte plaintext
     *   a4 = pointer to 16-byte state mask
     *   a5 = pointer to 16-byte ciphertext output
     */
    la a0, aes_context
    la a1, aes_key_share0     /* TAINT SOURCE (masked key share) */
    la a2, aes_key_mask
    la a3, aes_plaintext
    la a4, aes_state_mask
    la a5, aes_ciphertext

    /* Call the masked AES encryption function */
    call aes128_masked_encrypt

    /* Done - infinite loop */
infinite_loop:
    j infinite_loop


/*
 * ==========================================================================
 * DATA SECTION - Tainted Key Share
 * ==========================================================================
 * The AES key share is placed in a special .tainted_data section.
 * In CellIFT simulation, mark this memory region as tainted.
 */

  .section ".tainted_data","aw",@progbits
  .align 4

/*
 * AES-128 Secret Key Share (16 bytes) - TAINT SOURCE
 *
 * key_share0 = key ^ key_mask
 * key_mask is stored in .data (not tainted)
 */
  .globl aes_key_share0
 aes_key_share0:
     .byte 0xf0, 0xe0, 0xd0, 0xc0
     .byte 0xb0, 0xa0, 0x90, 0x80
     .byte 0x70, 0x60, 0x50, 0x40
     .byte 0x30, 0x20, 0x10, 0x00


/*
 * ==========================================================================
 * DATA SECTION - Public Data (not tainted)
 * ==========================================================================
 */

  .section ".data","aw",@progbits
  .align 4

/*
 * Key mask (16 bytes) - NOT tainted
 */
  .globl aes_key_mask
 aes_key_mask:
    .byte 0x0f, 0x1e, 0x2d, 0x3c
    .byte 0x4b, 0x5a, 0x69, 0x78
    .byte 0x87, 0x96, 0xa5, 0xb4
    .byte 0xc3, 0xd2, 0xe1, 0xf0

/*
 * State mask (16 bytes) - NOT tainted
 * Used to keep the AES state masked during rounds.
 */
  .globl aes_state_mask
 aes_state_mask:
    .byte 0x14, 0x98, 0x54, 0x55
    .byte 0x83, 0x42, 0xc8, 0x3f
    .byte 0x74, 0x56, 0xd0, 0xf8
    .byte 0xff, 0x89, 0x85, 0x9b

/*
 * Plaintext input block (16 bytes) - NOT tainted
 * FIPS-197 Appendix B test vector
 */
  .globl aes_plaintext
 aes_plaintext:
    .byte 0x66, 0x97, 0x15, 0xfb
    .byte 0x4c, 0x73, 0x7c, 0x4b
    .byte 0x9c, 0x6d, 0x9d, 0xef
    .byte 0x28, 0x30, 0x0d, 0x20

/*
 * Ciphertext output block (16 bytes)
 * Will become tainted after encryption.
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
