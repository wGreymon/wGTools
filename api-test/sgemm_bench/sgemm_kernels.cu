// Contiguous row-major FP32: C[M,N] = A[M,K] * B[K,N], alpha=1, beta=0.
// Launch metadata: decimal integer literals, read by benchmark.py.
// Each block owns one TILE_M x TILE_N output tile; adjust these to your implementation.
#define SGEMM_TILE_M 16
#define SGEMM_TILE_N 16
#define SGEMM_BLOCK_X 16
#define SGEMM_BLOCK_Y 16
#define SGEMM_SHARED_BYTES 0

extern "C" __global__ void sgemm_custom(
    const float* __restrict__ a,
    const float* __restrict__ b,
    float* __restrict__ c,
    int m, int n, int k) {
    // TODO: Implement SGEMM.
}
