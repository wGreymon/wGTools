// Contiguous row-major FP32: C[M,N] = A[M,K] * B[K,N], alpha=1, beta=0.
extern "C" __global__ void sgemm_custom(
    const float* __restrict__ a,
    const float* __restrict__ b,
    float* __restrict__ c,
    int m, int n, int k) {
    // TODO: Implement SGEMM.
}
