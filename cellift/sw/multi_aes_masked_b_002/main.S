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
    .byte 0xd5, 0x0b, 0x7d, 0x62
    .byte 0xbe, 0x29, 0x5c, 0xbb
    .byte 0xcc, 0xdf, 0x5e, 0x3b
    .byte 0xb2, 0x1f, 0x2a, 0x5a

/*
 * Plaintext input block (16 bytes) - NOT tainted
 * FIPS-197 Appendix B test vector
 */
  .globl aes_plaintext
 aes_plaintext:
    .byte 0xc4, 0xc1, 0xe0, 0xfe
    .byte 0x9a, 0x52, 0xea, 0x87
    .byte 0xa6, 0xc9, 0x69, 0x2a
    .byte 0x63, 0x93, 0xa5, 0xd3

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
