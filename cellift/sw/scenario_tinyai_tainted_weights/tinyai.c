/*
 * Simple 3x3 Matrix-Vector Multiplication for Power Side-Channel Analysis
 * 
 * Minimal example for CellIFT on Ibex (RV32IMC).
 * Computes: output = weights * input (3x3 matrix times 3x1 vector)
 * 
 * Uses 8-bit unsigned integers for weights to simplify power analysis.
 */

#include <stdint.h>

#define SIZE 3

/*
 * Matrix-vector multiplication: output = weights * input
 * 
 * Parameters:
 *   input   - Input vector (3 elements, uint8_t)
 *   weights - 3x3 weight matrix (9 elements, uint8_t) - TAINTED
 *   output  - Output vector (3 elements, uint16_t to avoid overflow)
 * 
 * Layout: weights[row][col] stored as weights[row * SIZE + col]
 */
void mat_vec_mul(const uint8_t *input,
                 const uint8_t *weights,
                 uint16_t *output)
{
    for (int i = 0; i < SIZE; i++) {
        uint16_t sum = 0;
        for (int j = 0; j < SIZE; j++) {
            /* Multiply-accumulate: taint spreads from weights */
            sum += (uint16_t)weights[i * SIZE + j] * (uint16_t)input[j];
        }
        output[i] = sum;
    }
}
