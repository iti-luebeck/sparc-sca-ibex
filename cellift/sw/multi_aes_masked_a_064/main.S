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
     .byte 0x0f, 0x1f, 0x2f, 0x3f
     .byte 0x4f, 0x5f, 0x6f, 0x7f
     .byte 0x8f, 0x9f, 0xaf, 0xbf
     .byte 0xcf, 0xdf, 0xef, 0xff


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
    .byte 0x61, 0x43, 0xb4, 0xe1
    .byte 0xf5, 0xda, 0xe2, 0x90
    .byte 0x87, 0x18, 0xb5, 0x75
    .byte 0x29, 0x3b, 0x71, 0x31

/*
 * Plaintext input block (16 bytes) - NOT tainted
 * FIPS-197 Appendix B test vector
 */
  .globl aes_plaintext
 aes_plaintext:
    .byte 0x4f, 0x02, 0x41, 0x20
    .byte 0x32, 0x30, 0x28, 0x9d
    .byte 0xf8, 0xd4, 0x52, 0x38
    .byte 0xe8, 0xad, 0x01, 0x11

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
