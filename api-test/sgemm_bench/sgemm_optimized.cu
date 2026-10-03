// Optimized FP32, contiguous row-major C[M,N] = A[M,K] * B[K,N], alpha=1, beta=0.
// One exported kernel. Keep its dispatch rules in sync with kernel_launcher.
// NVRTC supplies CUDA builtins; no headers or host compiler are needed.
struct __align__(16) Vec4 { float x, y, z, w; };

template<bool FULL>
__device__ __forceinline__ Vec4 load4(const float* ptr, bool active, int count, bool aligned) {
    Vec4 v = {};
    if (FULL || (active && count >= 4 && aligned)) {
        v = *reinterpret_cast<const Vec4*>(ptr);
    } else if (active) {
        if (count > 0) v.x = ptr[0];
        if (count > 1) v.y = ptr[1];
        if (count > 2) v.z = ptr[2];
        if (count > 3) v.w = ptr[3];
    }
    return v;
}

template<bool FULL>
__device__ __forceinline__ void store4(float* c, Vec4 v, int row, int col, int m, int n) {
    float* ptr = c + (unsigned long long)row * n + col;
    if (FULL || (n % 4 == 0 && row < m && col + 3 < n)) {
        *reinterpret_cast<Vec4*>(ptr) = v;
    } else if (row < m) {
        if (col < n) ptr[0] = v.x;
        if (col + 1 < n) ptr[1] = v.y;
        if (col + 2 < n) ptr[2] = v.z;
        if (col + 3 < n) ptr[3] = v.w;
    }
}

template<int BM, int BN, int BK, int LOAD_THREADS, bool FULL>
__device__ __forceinline__ void fetch(
    const float* a, const float* b, Vec4* va, Vec4* vb,
    int m, int n, int k, int rs, int cs, unsigned int base, int worker) {
    #pragma unroll
    for (int i = 0; i < BM * BK / (4 * LOAD_THREADS); ++i) {
        const int q = worker + i * LOAD_THREADS;
        const int row = rs + q / (BK / 4);
        const unsigned int p = base + q % (BK / 4) * 4;
        va[i] = load4<FULL>(a + (unsigned long long)row * k + p,
                           row < m, (int)((long long)k - p), k % 4 == 0);
    }
    #pragma unroll
    for (int i = 0; i < BK * BN / (4 * LOAD_THREADS); ++i) {
        const int q = worker + i * LOAD_THREADS;
        const unsigned int p = base + q / (BN / 4);
        const int col = cs + q % (BN / 4) * 4;
        vb[i] = load4<FULL>(b + (unsigned long long)p * n + col,
                           p < k, n - col, n % 4 == 0);
    }
}

template<int BM, int BN, int BK, int LOAD_THREADS>
__device__ __forceinline__ void stage(
    float* sa, float* sb, const Vec4* va, const Vec4* vb, int worker) {
    // Transpose A and swizzle row groups to spread writes across shared banks.
    #pragma unroll
    for (int i = 0; i < BM * BK / (4 * LOAD_THREADS); ++i) {
        const int q = worker + i * LOAD_THREADS;
        const int row = q / (BK / 4), p = q % (BK / 4) * 4;
        const int shared_row = row ^ (BM >= 32 ? (p / 4) * (32 / (BK / 4)) : 0);
        const Vec4 v = va[i];
        sa[p * BM + shared_row] = v.x;
        sa[(p + 1) * BM + shared_row] = v.y;
        sa[(p + 2) * BM + shared_row] = v.z;
        sa[(p + 3) * BM + shared_row] = v.w;
    }
    #pragma unroll
    for (int i = 0; i < BK * BN / (4 * LOAD_THREADS); ++i)
        *reinterpret_cast<Vec4*>(sb + (worker + i * LOAD_THREADS) * 4) = vb[i];
}

template<int SPLITS>
__device__ __forceinline__ void tile_barrier() {
    // Split-K warps own disjoint tiles and can have different iteration counts.
    if (SPLITS == 1) __syncthreads();
    else __syncwarp();
}

template<int BM, int BN, int WM, int WN, int SPLITS, int THREADS, bool FULL>
__device__ __forceinline__ void gemm_tile(
    const float* a, const float* b, float* c, int m, int n, int k, float* arena) {
    constexpr int BK = 16, TM = 4, TN = 4;
    constexpr int MI = WM * WN / (32 * TM * TN), SM = WM / MI;
    constexpr int LOAD_THREADS = SPLITS == 1 ? THREADS : 32;
    static_assert(WM * WN % (32 * TM * TN) == 0, "Invalid warp tile");
    static_assert(SPLITS == 1 ? THREADS == 32 * (BM / WM) * (BN / WN)
                              : THREADS == 32 * SPLITS && BM == WM && BN == WN,
                  "Thread count must match warp ownership");
    const int tid = threadIdx.x, warp = tid / 32, lane = tid % 32;
    const int group = SPLITS == 1 ? 0 : warp, worker = SPLITS == 1 ? tid : lane;
    const int wr = SPLITS == 1 ? warp / (BN / WN) : 0;
    const int wc = SPLITS == 1 ? warp % (BN / WN) : 0;
    const int lr = lane / (WN / TN), lc = lane % (WN / TN);
    int rs = blockIdx.y * BM, cs = blockIdx.x * BN;
    if (SPLITS == 1) {
        // Nearby blocks reuse B across four tile rows, and A across tile columns.
        const unsigned long long pid = (unsigned long long)blockIdx.y * gridDim.x + blockIdx.x;
        const unsigned long long group_size = 4ULL * gridDim.x;
        const unsigned int first_row = pid / group_size * 4;
        const unsigned int rows = min(gridDim.y - first_row, 4U);
        const unsigned int local = pid % group_size;
        rs = (first_row + local % rows) * BM;
        cs = (local / rows) * BN;
    }
    constexpr int TILE_STORAGE = BK * (BM + BN);
    float* sa = arena + group * 2 * TILE_STORAGE;
    float* sb = sa + BK * BM;
    float acc[MI * TM][TN] = {};
    Vec4 va[BM * BK / (4 * LOAD_THREADS)], vb[BK * BN / (4 * LOAD_THREADS)];
    const unsigned int chunk = ((unsigned int)k + BK * SPLITS - 1) / (BK * SPLITS) * BK;
    const unsigned int begin = group * chunk, end = min((unsigned int)k, begin + chunk);
    if (begin < end) {
        fetch<BM, BN, BK, LOAD_THREADS, FULL>(a, b, va, vb, m, n, k, rs, cs, begin, worker);
        stage<BM, BN, BK, LOAD_THREADS>(sa, sb, va, vb, worker);
        tile_barrier<SPLITS>();
    }
    int buffer = 0;
    for (unsigned int base = begin; base < end; base += BK) {
        // Prefetch into registers while computing the current shared-memory tile.
        const unsigned int next = base + BK;
        if (next < end)
            fetch<BM, BN, BK, LOAD_THREADS, FULL>(a, b, va, vb, m, n, k, rs, cs, next, worker);
        #pragma unroll
        for (int p = 0; p < BK; ++p) {
            float ra[MI * TM];
            #pragma unroll
            for (int i = 0; i < MI; ++i) {
                const int row = (wr * WM + i * SM + lr * TM) ^ (BM >= 32 ? (p / 4) * (32 / (BK / 4)) : 0);
                const Vec4 v = *reinterpret_cast<const Vec4*>(sa + p * BM + row);
                ra[i * TM] = v.x; ra[i * TM + 1] = v.y;
                ra[i * TM + 2] = v.z; ra[i * TM + 3] = v.w;
            }
            const Vec4 v = *reinterpret_cast<const Vec4*>(sb + p * BN + wc * WN + lc * TN);
            const float rb[TN] = {v.x, v.y, v.z, v.w};
            #pragma unroll
            for (int i = 0; i < MI * TM; ++i) {
                #pragma unroll
                for (int j = 0; j < TN; ++j) acc[i][j] = fmaf(ra[i], rb[j], acc[i][j]);
            }
        }
        if (next < end) {
            buffer ^= 1;
            float* next_sa = arena + group * 2 * TILE_STORAGE + buffer * TILE_STORAGE;
            float* next_sb = next_sa + BK * BM;
            stage<BM, BN, BK, LOAD_THREADS>(next_sa, next_sb, va, vb, worker);
            tile_barrier<SPLITS>();
            sa = next_sa;
            sb = next_sb;
        }
    }
    if (SPLITS > 1) {
        // Reuse tile storage for partial sums after all warps finish reading tiles.
        __syncthreads();
        float* partial = arena + warp * BM * BN;
        #pragma unroll
        for (int i = 0; i < MI; ++i) {
            #pragma unroll
            for (int ii = 0; ii < TM; ++ii) {
                const int row = i * SM + lr * TM + ii;
                const Vec4 v = {acc[i * TM + ii][0], acc[i * TM + ii][1],
                               acc[i * TM + ii][2], acc[i * TM + ii][3]};
                *reinterpret_cast<Vec4*>(partial + row * BN + lc * TN) = v;
            }
        }
        __syncthreads();
        for (int q = tid; q < BM * BN / 4; q += THREADS) {
            Vec4 sum = {};
            #pragma unroll
            for (int s = 0; s < SPLITS; ++s) {
                const Vec4 v = *reinterpret_cast<const Vec4*>(arena + s * BM * BN + q * 4);
                sum.x += v.x; sum.y += v.y; sum.z += v.z; sum.w += v.w;
            }
            store4<FULL>(c, sum, rs + q / (BN / 4), cs + q % (BN / 4) * 4, m, n);
        }
    } else {
        #pragma unroll
        for (int i = 0; i < MI; ++i) {
            #pragma unroll
            for (int ii = 0; ii < TM; ++ii) {
                const Vec4 v = {acc[i * TM + ii][0], acc[i * TM + ii][1],
                               acc[i * TM + ii][2], acc[i * TM + ii][3]};
                store4<FULL>(c, v, rs + wr * WM + i * SM + lr * TM + ii,
                             cs + wc * WN + lc * TN, m, n);
            }
        }
    }
}

template<int BM, int BN, int WM, int WN, int SPLITS, int THREADS>
__device__ __forceinline__ void dispatch_tile(
    const float* a, const float* b, float* c, int m, int n, int k, float* arena) {
    if (m % BM == 0 && n % BN == 0 && k % (16 * SPLITS) == 0)
        gemm_tile<BM, BN, WM, WN, SPLITS, THREADS, true>(a, b, c, m, n, k, arena);
    else
        gemm_tile<BM, BN, WM, WN, SPLITS, THREADS, false>(a, b, c, m, n, k, arena);
}

extern "C" __global__ __launch_bounds__(256) void sgemm_custom(
    const float* __restrict__ a, const float* __restrict__ b,
    float* __restrict__ c, int m, int n, int k) {
    extern __shared__ __align__(16) float arena[];
    const unsigned long long outputs = (unsigned long long)m * n;
    if (k == 1 || min(m, n) == 1 || (outputs <= 4096 && k <= 64) || (outputs <= 32768 && k <= 33)) {
        const unsigned long long q = (unsigned long long)blockIdx.x * blockDim.x + threadIdx.x;
        if (q < outputs) {
            unsigned long long row;
            unsigned int col;
            if (m == 1) { row = 0; col = q; }
            else if (n == 1) { row = q; col = 0; }
            else if (outputs <= 0xffffffffULL) {
                row = (unsigned int)q / (unsigned int)n;
                col = (unsigned int)q % (unsigned int)n;
            } else {
                row = q / (unsigned int)n;
                col = q % (unsigned int)n;
            }
            if (k == 1) {
                c[q] = a[row] * b[col];
            } else {
                float sum = 0;
                #pragma unroll 8
                for (int p = 0; p < k; ++p) sum = fmaf(a[row * k + p], b[(unsigned long long)p * n + col], sum);
                c[q] = sum;
            }
        }
    } else if (n < 32) {
        dispatch_tile<32, 16, 32, 16, 4, 128>(a, b, c, m, n, k, arena);
    } else if (m < 32 || outputs <= 32768) {
        dispatch_tile<16, 32, 16, 32, 8, 256>(a, b, c, m, n, k, arena);
    } else if (((unsigned long long)m + 63) / 64 * (((unsigned long long)n + 63) / 64) < 32 && k >= 128) {
        dispatch_tile<32, 32, 32, 32, 4, 128>(a, b, c, m, n, k, arena);
    } else {
        dispatch_tile<64, 64, 32, 32, 1, 128>(a, b, c, m, n, k, arena);
    }
}
