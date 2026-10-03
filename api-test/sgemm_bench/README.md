# CUDA 代码生成与优化能力评测

测试 `C[M,N] = A[M,K] × B[K,N]`，矩阵连续、按行存储，输入、输出和累加均为 FP32，`alpha=1, beta=0`。

- `sgemm_kernels.cu`：唯一的待实现文件，仅提供空的 `sgemm_custom` 接口和启动参数，由被测模型实现并优化。
- `benchmark.py`：Python 标准库测试入口，通过 ctypes 调用 CUDA Driver API、NVRTC 和 cuBLAS。NVRTC 将 CUDA 算子编译为本机 GPU 的 CUBIN，不需要 nvcc、MSVC、NumPy 或 PyTorch。

被测模型只修改 `sgemm_kernels.cu`，评测方运行 `benchmark.py`，根据正确性、性能及通过样例数判断能力。benchmark 中的测试尺寸、参考实现、计时和评分逻辑由评测方维护。

## 运行

需要 64 位 Python 3.9+、NVIDIA GPU 驱动及 CUDA Toolkit 11.1+，包含 NVRTC 和 cuBLAS。Toolkit 必须支持本机 GPU 的计算能力。支持 Windows x64 和 Linux x64；本机验证环境为 Windows、CUDA 13.4、RTX 4060 Laptop GPU。

在项目根目录执行：

```powershell
python api-test/sgemm_bench/benchmark.py
```

默认使用已审阅的 **50 组 shape**，顺序均为 `(M,N,K)`，完整清单位于 `benchmark.py` 的 `DEFAULT_SHAPES`。固定对比自定义 kernel 与 cuBLAS，每组进行全量输出校验及默认 32 个位置的独立 CPU 校验。

先让被测模型实现 `sgemm_kernels.cu`，再运行上述命令。空模板不写入输出，会被正确性检查判为失败。

| 测试类型 | 数量 | shape 范围或示例 |
|---|---:|---|
| 方阵 | 8 | 边长 32、64、128、256、512、1024、2048、4096 |
| 宽矩阵 | 3 | `(M,4096,1024)`，M 为 16、64、256 |
| 高矩阵 | 3 | `(4096,N,1024)`，N 为 16、64、256 |
| 短 K | 4 | `(2048,2048,K)`，K 为 16、32、64、128 |
| 长 K | 3 | `(256,256,K)`，K 为 2048、4096、8192 |
| 一般矩形 | 2 | `(1024,2048,512)`、`(2048,1024,512)` |
| 多维度非对齐 | 3 | `(513,777,259)`、`(1023,1025,1001)`、`(2047,2049,1023)` |
| M 分块边界 | 6 | `(M,128,256)`，M 为 63、64、65、127、128、129 |
| N 分块边界 | 5 | `(128,N,256)`，N 为 63、64、65、127、129；N=128 已在上一组覆盖 |
| K 分块边界 | 6 | `(128,128,K)`，K 为 15、16、17、31、32、33 |
| 单行、单列、K=1 和小尺寸边界 | 7 | `(1,1,1)`、`(1,129,7)`、`(129,1,17)`、`(129,131,1)`、`(17,19,23)`、`(65,67,33)`、`(129,131,127)` |

指定 `--sizes` 或 `--shape` 时使用指定尺寸；两者同时指定时合并指定尺寸。结果直接输出到终端，每个 shape 一行。

```powershell
# 比较自定义 kernel 和 cuBLAS
python api-test/sgemm_bench/benchmark.py --sizes 256 512 1024

# 指定 M、N、K，可以重复指定 --shape
python api-test/sgemm_bench/benchmark.py --shape 513,777,259 --shape 1024,2048,512

# 更大的方阵，增加预热和测量轮数
python api-test/sgemm_bench/benchmark.py --sizes 2048 4096 --warmup 20 --iterations 100 --repeats 7

# 快速边界检查；CPU 检查所有输出元素
python api-test/sgemm_bench/benchmark.py --shape 17,19,23 --cpu-samples 323 --iterations 10

python api-test/sgemm_bench/benchmark.py --help
```

Windows 优先从 `CUDA_PATH` 和 Toolkit 安装目录查找 DLL，兼容 CUDA 13 的 `bin/x64` 目录。Linux 可设置 `CUDA_HOME` 和 `LD_LIBRARY_PATH`。找不到库时会报告尝试过的路径。

## 指标与测试方法

终端按**每个 shape 一行**输出，将 shape 合并为 `MxNxK`，使用两层表头：上层按时间、算力、误差、加速比和检查结果分组，下层标明 custom、cuBLAS 以及正确性 `Corr`、性能 `Perf`，组间使用竖线分隔。默认 50 组尺寸的表格宽度为 82 字符；80 列终端会自动使用更紧凑的格式，C/B 分别表示 custom/cuBLAS。重复指定的 shape 自动去重，保留首次出现的顺序。

- **时间 `Time(ms)`**：custom 和 cuBLAS 的耗时，单位为毫秒。默认先把一批连续调用捕获为 CUDA Graph，再使用同一 CUDA Stream 的 CUDA Event 测量 Graph 回放时间，除以调用次数；报告多轮结果的中位数。分配内存、编译、数据拷贝、预热、Graph 构建和首次回放、正确性校验都在计时区间之外。
- **算力 `GFLOPS`**：custom 和 cuBLAS 的实际吞吐量，使用 `GFLOPS = 2×M×N×K / (time_ms×10^6)` 计算。
- **误差 `Err(max)`**：自定义 kernel 与 cuBLAS 相比，全部输出元素中的最大绝对误差。
- **加速比 `Speed(x)`**：cuBLAS 耗时 / 自定义 kernel 耗时。例如 `0.25` 表示自定义 kernel 的耗时是 cuBLAS 的 4 倍，`2.0` 表示自定义 kernel 快 2 倍。
- **正确性 `Corr`**：该 shape 通过全量输出比较及已启用的 CPU 校验后显示 `✓`。校验失败会报告错误并返回非零退出码。
- **性能 `Perf`**：加速比严格大于 `0.80` 时显示 `✓`，小于或等于 `0.80` 显示 `✗`。这等价于 custom 的 GFLOPS 超过 cuBLAS 的 80%，或 custom 耗时小于 cuBLAS 耗时的 1.25 倍。判定使用未舍入的测量值，终端显示的加速比保留三位小数。性能未达标会继续测试后续 shape；正常完成测试时退出码为 0。
- cuBLAS 设置 `CUBLAS_PEDANTIC_MATH`，关闭 TF32 等降低乘法精度的路径，保持 FP32 对比。按行矩阵通过 `Cᵀ=Bᵀ×Aᵀ` 调用列优先的 `cublasSgemm`，无需转置或额外拷贝。
- 每个手写结果都与 cuBLAS 的**全部输出元素**比较，满足 `abs(actual-reference) <= atol + rtol×abs(reference)`；另外默认抽查 32 个位置，以 Python FP64 乘法和 `math.fsum` 的结果进行独立检查。输出先填充 NaN，漏写或非有限结果会被发现。失败时程序返回非零退出码。

正常完成测试后，终端末尾输出样例数、检查总数，以及正确性 `Corr`、性能 `Perf`、两项都通过 `Both` 的样例数。默认 50 个样例对应 100 项检查；指定尺寸时按去重后的实际样例数统计。`Both` 表示通过的样例总数，一个样例必须同时通过正确性和性能检查。

这里测量的是相同输入反复计算时的性能，可能命中 GPU 缓存。各实现的测量顺序轮换，以减小温度和频率变化的影响。默认 `--timing graph` 减少 Python 提交调用产生的 GPU 空闲间隙，测量的是 Graph 执行方式下的性能，包含 Graph 内各节点的调度开销。可使用 `--timing launch` 测量普通连续调用，但小矩阵成绩会受到 Python 提交开销明显影响；CUDA Event 时间无法排除 GPU 等待下一次提交的时间。

笔记本 GPU 的功耗设置和温度会影响成绩。建议接通电源，在相同设置、相近温度下测量。FP32 实现的累加顺序不同，结果允许一定浮点误差；更大的 K 可能需要按精度要求调整 `--atol` 和 `--rtol`。

## 被测方实现接口

只修改 `sgemm_kernels.cu`，实现以下唯一的 kernel 接口；可添加设备辅助函数：

```cpp
extern "C" __global__ void sgemm_custom(
    const float* a, const float* b, float* c,
    int m, int n, int k);
```

同一文件中的宏声明启动参数，benchmark 自动读取，无需修改测试脚本。每个宏只能定义一次，值必须是十进制整数字面量；省略时使用下表中的默认值。

| 宏 | 默认值 | 含义 |
|---|---:|---|
| `SGEMM_TILE_M` | 16 | 每个线程块覆盖的输出行数 |
| `SGEMM_TILE_N` | 16 | 每个线程块覆盖的输出列数 |
| `SGEMM_BLOCK_X` | 16 | 线程块 X 维度 |
| `SGEMM_BLOCK_Y` | 16 | 线程块 Y 维度 |
| `SGEMM_SHARED_BYTES` | 0 | 每个线程块的动态共享内存字节数 |

启动方式固定为 `block=(SGEMM_BLOCK_X,SGEMM_BLOCK_Y,1)`、`grid=(ceil(N/SGEMM_TILE_N),ceil(M/SGEMM_TILE_M),1)`，动态共享内存按 `SGEMM_SHARED_BYTES` 分配。默认是 16×16 输出块和 16×16 线程块；被测模型可在该文件内调整分块、线程数量和共享内存，并自行决定计算算法。

算子必须覆盖所有输出、支持矩形和边界尺寸，且不依赖 C 的初值。只运行一个自定义 kernel，乘法和累加均使用 FP32，不得调用 cuBLAS 或使用 TF32、FP16 等降低精度的替代路径。

范围：连续矩阵、单次非批量 SGEMM、无转置、无自定义 leading dimension；不包含 H2D/D2H 时间，也不测试 TF32 或 FP16 Tensor Core 性能。
