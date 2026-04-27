/*
 * AES-128 Masked Key Vector Scenario - Ibex Core
 */

#include <stdint.h>

#ifndef VECTOR_HEADER
#error "VECTOR_HEADER not defined"
#endif

#include VECTOR_HEADER

#define AES_BLOCK_SIZE 16

/* Provided by aes128_masked.c */
void aes128_masked_encrypt(uint8_t *ctx,
                           const uint8_t *key_share0,
                           const uint8_t *key_mask,
                           const uint8_t *plaintext,
                           const uint8_t *state_mask,
                           uint8_t *ciphertext);

static uint8_t aes_context[176];
static uint8_t aes_ciphertext[AES_BLOCK_SIZE];

void c_main(void)
{
    aes128_masked_encrypt(aes_context,
                          aes_key_share0,
                          aes_key_mask,
                          aes_plaintext,
                          aes_state_mask,
                          aes_ciphertext);

    /* Endless loop */
    while (1) {
        /* spin */
    }
}
