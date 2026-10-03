#!/usr/bin/env python3
"""Benchmark one custom CUDA SGEMM kernel against cuBLAS, using Python's stdlib."""

import argparse
from array import array
import ctypes as ct
import ctypes.util
import glob
import math
import os
from pathlib import Path
import random
import re
import shutil
import statistics
import sys


PTR = ct.c_void_p
INT = ct.c_int
UINT = ct.c_uint
SIZE = ct.c_size_t
DEVICE_PTR = ct.c_uint64
FLOAT = ct.c_float
PERFORMANCE_THRESHOLD = 0.80
PASS_SYMBOL = "\u2713"
FAIL_SYMBOL = "\u2717"


def parse_launch_config(source):
    """Read launch metadata from the submitted source without executing host code."""
    config = {"SGEMM_TILE_M": 16, "SGEMM_TILE_N": 16,
              "SGEMM_BLOCK_X": 16, "SGEMM_BLOCK_Y": 16,
              "SGEMM_SHARED_BYTES": 0}
    names = "|".join(config)
    seen = set()
    for name, text in re.findall(rf"^\s*#\s*define\s+({names})\b([^\r\n]*)", source, re.M):
        if name in seen:
            raise ValueError(f"Define {name} only once.")
        seen.add(name)
        value = re.fullmatch(r"\s*([0-9]+)\s*(?://.*)?", text)
        if not value:
            raise ValueError(f"{name} must be a decimal integer literal.")
        config[name] = int(value.group(1))
        if name != "SGEMM_SHARED_BYTES" and config[name] == 0:
            raise ValueError(f"{name} must be positive.")
    return config


# Approved test suite. Each tuple is (M, N, K): A[M,K] * B[K,N] -> C[M,N].
DEFAULT_SHAPES = (
    # Square matrices: small, medium, and large.
    (32, 32, 32),
    (64, 64, 64),
    (128, 128, 128),
    (256, 256, 256),
    (512, 512, 512),
    (1024, 1024, 1024),
    (2048, 2048, 2048),
    (4096, 4096, 4096),
    # Wide matrices: small M.
    (16, 4096, 1024),
    (64, 4096, 1024),
    (256, 4096, 1024),
    # Tall matrices: small N, paired with the wide cases.
    (4096, 16, 1024),
    (4096, 64, 1024),
    (4096, 256, 1024),
    # Short K.
    (2048, 2048, 16),
    (2048, 2048, 32),
    (2048, 2048, 64),
    (2048, 2048, 128),
    # Long K.
    (256, 256, 2048),
    (256, 256, 4096),
    (256, 256, 8192),
    # General rectangular matrices.
    (1024, 2048, 512),
    (2048, 1024, 512),
    # Multiple unaligned dimensions.
    (513, 777, 259),
    (1023, 1025, 1001),
    (2047, 2049, 1023),
    # M tile boundaries; fix N and K.
    (63, 128, 256),
    (64, 128, 256),
    (65, 128, 256),
    (127, 128, 256),
    (128, 128, 256),
    (129, 128, 256),
    # N tile boundaries; (128,128,256) is already included above.
    (128, 63, 256),
    (128, 64, 256),
    (128, 65, 256),
    (128, 127, 256),
    (128, 129, 256),
    # K tile boundaries; fix M and N.
    (128, 128, 15),
    (128, 128, 16),
    (128, 128, 17),
    (128, 128, 31),
    (128, 128, 32),
    (128, 128, 33),
    # Single rows/columns, K=1, and small edge cases.
    (1, 1, 1),
    (1, 129, 7),
    (129, 1, 17),
    (129, 131, 1),
    (17, 19, 23),
    (65, 67, 33),
    (129, 131, 127),
)


def bind(library, name, arguments):
    function = getattr(library, name)
    function.restype = INT
    function.argtypes = arguments
    return function


class CudaLibraries:
    """Find DLLs/shared libraries without modifying the system environment."""

    def __init__(self):
        self.dll_directories = []
        roots = []
        for key in ("CUDA_PATH", "CUDA_HOME"):
            if os.environ.get(key):
                roots.append(Path(os.environ[key]))
        for key, value in os.environ.items():
            if key.startswith("CUDA_PATH_V"):
                roots.append(Path(value))
        if os.name == "nt":
            base = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            roots.extend(sorted((base / "NVIDIA GPU Computing Toolkit" / "CUDA").glob("v*"),
                                reverse=True))
        else:
            roots.extend([Path("/usr/local/cuda")])
            roots.extend(Path(p) for p in sorted(glob.glob("/usr/local/cuda-*"), reverse=True))

        self.directories = []
        for root in roots:
            for suffix in ("bin/x64", "bin", "lib64", "targets/x86_64-linux/lib", "lib"):
                directory = root / suffix
                if directory.is_dir() and directory not in self.directories:
                    self.directories.append(directory)
                    if os.name == "nt":
                        self.dll_directories.append(os.add_dll_directory(str(directory)))

        self.loader = ct.WinDLL if os.name == "nt" else ct.CDLL
        self.driver = self.load("driver")
        self.nvrtc = self.load("nvrtc")
        self.cublas = self.load("cublas")

    def load(self, kind):
        windows_patterns = {"nvrtc": "nvrtc64_*.dll", "cublas": "cublas64_*.dll"}
        linux_patterns = {"nvrtc": "libnvrtc.so*", "cublas": "libcublas.so*"}
        if kind == "driver":
            candidates = ["nvcuda.dll"] if os.name == "nt" else ["libcuda.so.1"]
        else:
            pattern = (windows_patterns if os.name == "nt" else linux_patterns)[kind]
            candidates = [str(path) for directory in self.directories
                          for path in sorted(directory.glob(pattern), reverse=True)]
            found = ct.util.find_library(kind)
            if found:
                candidates.append(found)
            if os.name == "nt":
                candidates.extend([f"{kind}64_130_0.dll"] if kind == "nvrtc"
                                  else ["cublas64_13.dll", "cublas64_12.dll"])
            else:
                candidates.append(f"lib{kind}.so")
        errors = []
        for candidate in candidates:
            try:
                return self.loader(candidate)
            except OSError as error:
                errors.append(f"{candidate}: {error}")
        detail = "\n".join(errors) or "No matching library was found."
        raise RuntimeError(f"Cannot load {kind}. Install the NVIDIA driver/CUDA Toolkit "
                           f"and set CUDA_PATH (Windows) or CUDA_HOME (Linux).\n{detail}")


class Gpu:
    def __init__(self, libraries, device_index):
        self.libraries = libraries
        driver = libraries.driver
        specifications = {
            "cuInit": [UINT],
            "cuDeviceGet": [ct.POINTER(INT), INT],
            "cuDeviceGetName": [PTR, INT, INT],
            "cuDeviceGetAttribute": [ct.POINTER(INT), INT, INT],
            "cuDriverGetVersion": [ct.POINTER(INT)],
            "cuDevicePrimaryCtxRetain": [ct.POINTER(PTR), INT],
            "cuDevicePrimaryCtxRelease_v2": [INT],
            "cuCtxSetCurrent": [PTR],
            "cuMemGetInfo_v2": [ct.POINTER(SIZE), ct.POINTER(SIZE)],
            "cuMemAlloc_v2": [ct.POINTER(DEVICE_PTR), SIZE],
            "cuMemFree_v2": [DEVICE_PTR],
            "cuMemsetD8Async": [DEVICE_PTR, ct.c_ubyte, SIZE, PTR],
            "cuMemcpyHtoD_v2": [DEVICE_PTR, PTR, SIZE],
            "cuMemcpyDtoH_v2": [PTR, DEVICE_PTR, SIZE],
            "cuStreamCreate": [ct.POINTER(PTR), UINT],
            "cuStreamDestroy_v2": [PTR],
            "cuStreamSynchronize": [PTR],
            "cuStreamBeginCapture": [PTR, INT],
            "cuStreamEndCapture": [PTR, ct.POINTER(PTR)],
            "cuGraphInstantiate_v2": [ct.POINTER(PTR), PTR, ct.POINTER(PTR), PTR, SIZE],
            "cuGraphLaunch": [PTR, PTR],
            "cuGraphDestroy": [PTR],
            "cuGraphExecDestroy": [PTR],
            "cuEventCreate": [ct.POINTER(PTR), UINT],
            "cuEventRecord": [PTR, PTR],
            "cuEventSynchronize": [PTR],
            "cuEventElapsedTime": [ct.POINTER(FLOAT), PTR, PTR],
            "cuEventDestroy_v2": [PTR],
            "cuModuleLoadData": [ct.POINTER(PTR), PTR],
            "cuModuleGetFunction": [ct.POINTER(PTR), PTR, ct.c_char_p],
            "cuModuleUnload": [PTR],
            "cuFuncSetAttribute": [PTR, INT, INT],
            "cuLaunchKernel": [PTR, UINT, UINT, UINT, UINT, UINT, UINT,
                               UINT, PTR, ct.POINTER(PTR), ct.POINTER(PTR)],
            "cuGetErrorName": [INT, ct.POINTER(ct.c_char_p)],
            "cuGetErrorString": [INT, ct.POINTER(ct.c_char_p)],
        }
        self.api = {name: bind(driver, name, args) for name, args in specifications.items()}
        self.context, self.stream, self.module, self.handle = PTR(), PTR(), PTR(), PTR()
        self.allocations, self.events, self.graphs, self.executables = [], [], [], []
        self.device = INT()
        self.retained = False
        self.call("cuInit", 0)
        self.call("cuDeviceGet", ct.byref(self.device), device_index)
        try:
            self.call("cuDevicePrimaryCtxRetain", ct.byref(self.context), self.device)
            self.retained = True
            self.call("cuCtxSetCurrent", self.context)
            self.call("cuStreamCreate", ct.byref(self.stream), 1)
            self.setup_cublas()
        except Exception:
            self.close()
            raise

    def call(self, name, *args):
        status = self.api[name](*args)
        if status:
            error_name, description = ct.c_char_p(), ct.c_char_p()
            self.api["cuGetErrorName"](status, ct.byref(error_name))
            self.api["cuGetErrorString"](status, ct.byref(description))
            raise RuntimeError(f"{name}: {(error_name.value or b'unknown').decode()} "
                               f"({(description.value or b'').decode()})")

    def setup_cublas(self):
        specifications = {
            "cublasCreate_v2": [ct.POINTER(PTR)],
            "cublasDestroy_v2": [PTR],
            "cublasSetStream_v2": [PTR, PTR],
            "cublasSetMathMode": [PTR, INT],
            "cublasSetPointerMode_v2": [PTR, INT],
            "cublasGetVersion_v2": [PTR, ct.POINTER(INT)],
            "cublasSgemm_v2": [PTR, INT, INT, INT, INT, INT, ct.POINTER(FLOAT),
                               PTR, INT, PTR, INT, ct.POINTER(FLOAT), PTR, INT],
        }
        self.blas = {name: bind(self.libraries.cublas, name, args)
                     for name, args in specifications.items()}
        self.blas_call("cublasCreate_v2", ct.byref(self.handle))
        self.blas_call("cublasSetStream_v2", self.handle, self.stream)
        self.blas_call("cublasSetPointerMode_v2", self.handle, 0)  # HOST scalars
        self.blas_call("cublasSetMathMode", self.handle, 2)  # CUBLAS_PEDANTIC_MATH

    def blas_call(self, name, *args):
        status = self.blas[name](*args)
        if status:
            names = {1: "NOT_INITIALIZED", 3: "ALLOC_FAILED", 7: "INVALID_VALUE",
                     8: "ARCH_MISMATCH", 11: "MAPPING_ERROR", 13: "EXECUTION_FAILED",
                     14: "INTERNAL_ERROR", 15: "NOT_SUPPORTED", 16: "LICENSE_ERROR"}
            raise RuntimeError(f"{name}: CUBLAS_STATUS_{names.get(status, str(status))}")

    def attribute(self, attribute):
        value = INT()
        self.call("cuDeviceGetAttribute", ct.byref(value), attribute, self.device)
        return value.value

    def describe(self):
        name, driver_version, blas_version = ct.create_string_buffer(256), INT(), INT()
        self.call("cuDeviceGetName", name, len(name), self.device)
        self.call("cuDriverGetVersion", ct.byref(driver_version))
        self.blas_call("cublasGetVersion_v2", self.handle, ct.byref(blas_version))
        return name.value.decode(), driver_version.value, blas_version.value

    def allocate(self, elements):
        pointer = DEVICE_PTR()
        self.call("cuMemAlloc_v2", ct.byref(pointer), elements * 4)
        self.allocations.append(pointer)
        return pointer

    def free_allocations(self):
        while self.allocations:
            self.call("cuMemFree_v2", self.allocations[-1])
            self.allocations.pop()

    def upload(self, pointer, values):
        address, count = values.buffer_info()
        self.call("cuMemcpyHtoD_v2", pointer, PTR(address), count * values.itemsize)
        # Pageable H2D may return after staging; our nonblocking stream needs completion.
        self.call("cuStreamSynchronize", PTR())

    def download(self, pointer, count):
        values = array("f", [0.0]) * count
        self.call("cuMemcpyDtoH_v2", PTR(values.buffer_info()[0]), pointer, count * 4)
        return values

    def poison(self, pointer, elements):
        # 0xffffffff is a NaN: validation catches any output a kernel fails to write.
        # Order initialization before computation on the same nonblocking stream.
        self.call("cuMemsetD8Async", pointer, 255, elements * 4, self.stream)

    def synchronize(self):
        self.call("cuStreamSynchronize", self.stream)

    def event(self):
        event = PTR()
        self.call("cuEventCreate", ct.byref(event), 0)
        self.events.append(event)
        return event

    def capture(self, launch, iterations):
        graph, executable = PTR(), PTR()
        self.call("cuStreamBeginCapture", self.stream, 0)
        try:
            for _ in range(iterations):
                launch()
        except Exception:
            self.api["cuStreamEndCapture"](self.stream, ct.byref(graph))
            if graph.value:
                self.api["cuGraphDestroy"](graph)
            raise
        self.call("cuStreamEndCapture", self.stream, ct.byref(graph))
        self.graphs.append(graph)
        self.call("cuGraphInstantiate_v2", ct.byref(executable), graph, None, None, 0)
        self.executables.append(executable)
        self.call("cuGraphDestroy", graph)
        self.graphs.remove(graph)
        return executable

    def compile(self, source):
        self.launch_config = parse_launch_config(source)
        library = self.libraries.nvrtc
        specifications = {
            "nvrtcVersion": [ct.POINTER(INT), ct.POINTER(INT)],
            "nvrtcCreateProgram": [ct.POINTER(PTR), ct.c_char_p, ct.c_char_p,
                                   INT, ct.POINTER(ct.c_char_p), ct.POINTER(ct.c_char_p)],
            "nvrtcCompileProgram": [PTR, INT, ct.POINTER(ct.c_char_p)],
            "nvrtcGetProgramLogSize": [PTR, ct.POINTER(SIZE)],
            "nvrtcGetProgramLog": [PTR, PTR],
            "nvrtcGetCUBINSize": [PTR, ct.POINTER(SIZE)],
            "nvrtcGetCUBIN": [PTR, PTR],
            "nvrtcDestroyProgram": [ct.POINTER(PTR)],
        }
        api = {name: bind(library, name, args) for name, args in specifications.items()}

        def check(name, *args):
            status = api[name](*args)
            if status:
                raise RuntimeError(f"{name}: NVRTC error {status}")

        major, minor = INT(), INT()
        check("nvrtcVersion", ct.byref(major), ct.byref(minor))
        architecture = f"sm_{self.attribute(75)}{self.attribute(76)}"
        options = (ct.c_char_p * 2)(f"--gpu-architecture={architecture}".encode(),
                                   b"--std=c++14")
        program = PTR()
        check("nvrtcCreateProgram", ct.byref(program), source.encode(),
              b"sgemm_kernels.cu", 0, None, None)
        try:
            status = api["nvrtcCompileProgram"](program, len(options), options)
            log_size = SIZE()
            check("nvrtcGetProgramLogSize", program, ct.byref(log_size))
            log = ct.create_string_buffer(max(1, log_size.value))
            check("nvrtcGetProgramLog", program, log)
            if status:
                raise RuntimeError(f"NVRTC compilation failed ({status}):\n{log.value.decode()}")
            if log.value:
                print(log.value.decode(), file=sys.stderr)
            cubin_size = SIZE()
            check("nvrtcGetCUBINSize", program, ct.byref(cubin_size))
            cubin = ct.create_string_buffer(cubin_size.value)
            check("nvrtcGetCUBIN", program, cubin)
            # Native CUBIN avoids requiring the driver to understand newer PTX versions.
            self.call("cuModuleLoadData", ct.byref(self.module), cubin)
        finally:
            check("nvrtcDestroyProgram", ct.byref(program))
        return architecture, f"{major.value}.{minor.value}"

    def kernel_launcher(self, a, b, c, m, n, k):
        function = PTR()
        self.call("cuModuleGetFunction", ct.byref(function), self.module,
                  b"sgemm_custom")
        config = self.launch_config
        tile_m, tile_n = config["SGEMM_TILE_M"], config["SGEMM_TILE_N"]
        block_x, block_y = config["SGEMM_BLOCK_X"], config["SGEMM_BLOCK_Y"]
        shared_bytes = config["SGEMM_SHARED_BYTES"]
        grid_x, grid_y = (n + tile_n - 1) // tile_n, (m + tile_m - 1) // tile_m
        if (block_x > self.attribute(2) or block_y > self.attribute(3)
                or block_x * block_y > self.attribute(1)):
            raise ValueError("Submitted block dimensions exceed CUDA device limits.")
        if shared_bytes > self.attribute(8):
            if shared_bytes > self.attribute(97):
                raise ValueError("Submitted dynamic shared memory exceeds CUDA device limits.")
            self.call("cuFuncSetAttribute", function, 8, shared_bytes)
        if grid_x > self.attribute(5) or grid_y > self.attribute(6):
            raise ValueError("Shape exceeds CUDA grid limits for the custom kernel.")
        # Keep argument storage alive for all asynchronous launches.
        arguments = (DEVICE_PTR(a.value), DEVICE_PTR(b.value), DEVICE_PTR(c.value),
                     INT(m), INT(n), INT(k))
        parameters = (PTR * len(arguments))(*(ct.cast(ct.pointer(arg), PTR)
                                             for arg in arguments))

        def launch():
            self.call("cuLaunchKernel", function, grid_x, grid_y, 1,
                      block_x, block_y, 1, shared_bytes, self.stream, parameters, None)
            _ = arguments
        return launch

    def cublas_launcher(self, a, b, c, m, n, k):
        alpha, beta = FLOAT(1.0), FLOAT(0.0)

        def launch():
            # Row-major C = A*B becomes column-major C^T = B^T*A^T.
            self.blas_call("cublasSgemm_v2", self.handle, 0, 0, n, m, k,
                           ct.byref(alpha), PTR(b.value), n, PTR(a.value), k,
                           ct.byref(beta), PTR(c.value), n)
        return launch

    def close(self):
        # Cleanup must not replace an earlier compilation/launch/validation error.
        if self.stream.value:
            self.api["cuStreamSynchronize"](self.stream)
        for executable in self.executables:
            self.api["cuGraphExecDestroy"](executable)
        self.executables.clear()
        for graph in self.graphs:
            self.api["cuGraphDestroy"](graph)
        self.graphs.clear()
        if self.handle.value:
            self.blas["cublasDestroy_v2"](self.handle)
            self.handle = PTR()
        for event in self.events:
            self.api["cuEventDestroy_v2"](event)
        self.events.clear()
        if self.module.value:
            self.api["cuModuleUnload"](self.module)
            self.module = PTR()
        for pointer in self.allocations:
            self.api["cuMemFree_v2"](pointer)
        self.allocations.clear()
        if self.stream.value:
            self.api["cuStreamDestroy_v2"](self.stream)
            self.stream = PTR()
        if self.retained:
            self.api["cuDevicePrimaryCtxRelease_v2"](self.device)
            self.retained = False


def verify(actual, reference, atol, rtol):
    failures, max_absolute, max_scaled = 0, 0.0, 0.0
    for value, expected in zip(actual, reference):
        if not math.isfinite(value) or not math.isfinite(expected):
            failures += 1
            max_absolute = max_scaled = math.inf
            continue
        error = abs(value - expected)
        limit = atol + rtol * abs(expected)
        scaled = error / limit
        failures += error > limit
        max_absolute = max(max_absolute, error)
        max_scaled = max(max_scaled, scaled)
    return failures, max_absolute, max_scaled


def verify_cpu(outputs, a, b, m, n, k, samples, atol, rtol, seed):
    count = m * n
    if samples == 0:
        return
    if samples >= count:
        indices = range(count)
    else:
        # Include tile edges and the last row/column, then add deterministic samples.
        boundaries = {0, n - 1, (m - 1) * n, count - 1,
                      min(m - 1, 63) * n + min(n - 1, 63),
                      min(m - 1, 64) * n + min(n - 1, 64)}
        indices = sorted(boundaries)[:samples]
        selected = set(indices)
        rng = random.Random(seed)
        while len(indices) < min(samples, count):
            index = rng.randrange(count)
            if index not in selected:
                selected.add(index)
                indices.append(index)
    for index in indices:
        row, col = divmod(index, n)
        expected = math.fsum(float(a[row * k + p]) * float(b[p * n + col])
                             for p in range(k))
        for name, values in outputs.items():
            value = values[index]
            if not math.isfinite(value) or abs(value - expected) > atol + rtol * abs(expected):
                raise RuntimeError(f"CPU validation failed: {name}, C[{row},{col}]="
                                   f"{value:.9g}, expected {expected:.9g}")


def measure(gpu, launchers, iterations, repeats, warmup, timing):
    for launch in launchers.values():
        for _ in range(warmup):
            launch()
    gpu.synchronize()
    graphs = {}
    if timing == "graph":
        graphs = {name: gpu.capture(launch, iterations) for name, launch in launchers.items()}
        # First graph replay can perform upload/setup. Keep it out of measured batches.
        for graph in graphs.values():
            gpu.call("cuGraphLaunch", graph, gpu.stream)
        gpu.synchronize()
    start, stop = gpu.event(), gpu.event()
    samples = {name: [] for name in launchers}
    names = list(launchers)
    for repeat in range(repeats):
        # Rotate order to reduce systematic effects from clock/temperature drift.
        order = names[repeat % len(names):] + names[:repeat % len(names)]
        for name in order:
            gpu.call("cuEventRecord", start, gpu.stream)
            if timing == "graph":
                gpu.call("cuGraphLaunch", graphs[name], gpu.stream)
            else:
                for _ in range(iterations):
                    launchers[name]()
            gpu.call("cuEventRecord", stop, gpu.stream)
            gpu.call("cuEventSynchronize", stop)
            elapsed = FLOAT()
            gpu.call("cuEventElapsedTime", ct.byref(elapsed), start, stop)
            if elapsed.value <= 0:
                raise RuntimeError("CUDA event timing was zero; increase --iterations.")
            samples[name].append(elapsed.value / iterations)
    for event in (start, stop):
        gpu.call("cuEventDestroy_v2", event)
        gpu.events.remove(event)
    for graph in graphs.values():
        gpu.call("cuGraphExecDestroy", graph)
        gpu.executables.remove(graph)
    return samples


class ConsoleTable:
    """Display one custom kernel and cuBLAS, with metrics grouped by purpose."""

    def __init__(self, shapes):
        self.shape_width = max(len("Shape(M,N,K)"),
                               *(len("x".join(map(str, shape))) for shape in shapes))
        self.compact = False
        self.configure()
        if self.width > shutil.get_terminal_size(fallback=(120, 24)).columns:
            self.compact = True
            self.configure()

    def configure(self):
        time_width, rate_width, error_width, speed_width = (
            (5, 5, 6, 5) if self.compact else (7, 6, 8, 6))
        implementations = ("custom", "cublas")
        self.groups = [
            ("Time(ms)", [(name, "ms", time_width) for name in implementations]),
            ("GFLOPS", [(name, "gflops", rate_width) for name in implementations]),
            ("Err(max)", [("custom", "max_abs_err", error_width)]),
            ("Speed(x)", [("custom", "speedup", speed_width)]),
        ]
        self.group_widths = [max(len(label), sum(field[2] for field in fields) + len(fields) - 1)
                             for label, fields in self.groups]
        self.separator = "|" if self.compact else " | "
        self.widths = [self.shape_width, *self.group_widths, 9]
        self.width = sum(self.widths) + (len(self.widths) - 1) * len(self.separator)

    @staticmethod
    def short_number(value, style, width):
        rendered = format(value, style)
        if len(rendered) <= width:
            return rendered
        for precision in (2, 1, 0):
            mantissa, exponent = f"{value:.{precision}e}".split("e")
            rendered = f"{mantissa}e{int(exponent)}"
            if len(rendered) <= width:
                return rendered
        return rendered

    def header(self):
        if self.compact:
            print("C=custom, B=cuBLAS")
        labels = ["", *(label for label, _ in self.groups), "Check"]
        print(self.separator.join(f"{label:^{width}}" for label, width in zip(labels, self.widths)))
        aliases = {"custom": "C", "cublas": "B"} if self.compact else {
            "custom": "custom", "cublas": "cuBLAS"}
        subheaders = ["Shape(M,N,K)"]
        for (_, fields), width in zip(self.groups, self.group_widths):
            names = " ".join(f"{aliases[name]:>{field_width}}" for name, _, field_width in fields)
            subheaders.append(f"{names:>{width}}")
        subheaders.append("Corr Perf")
        print(self.separator.join(f"{label:<{width}}" for label, width in zip(subheaders, self.widths)))
        print("-" * self.width)

    def row(self, result):
        cells = ["x".join(str(result[key]) for key in ("M", "N", "K"))]
        styles = ({"ms": ".2g", "gflops": ".2g", "max_abs_err": ".1e", "speedup": ".3f"}
                  if self.compact else
                  {"ms": ".4f", "gflops": ".0f", "max_abs_err": ".1e", "speedup": ".3f"})
        for (_, fields), width in zip(self.groups, self.group_widths):
            values = " ".join(f"{self.short_number(result[name + '_' + metric], styles[metric], field_width):>{field_width}}"
                              for name, metric, field_width in fields)
            cells.append(f"{values:>{width}}")
        correctness = PASS_SYMBOL if result["correctness_check"] == "PASS" else FAIL_SYMBOL
        performance = PASS_SYMBOL if result["performance_check"] == "PASS" else FAIL_SYMBOL
        cells.append(f"{correctness:^4s} {performance:^4s}")
        print(self.separator.join(f"{cell:<{width}}" for cell, width in zip(cells, self.widths)), flush=True)


def summarize_results(shape, samples, max_absolute):
    m, n, k = shape
    custom_ms = statistics.median(samples["custom"])
    cublas_ms = statistics.median(samples["cublas"])
    speedup = cublas_ms / custom_ms
    return {"M": m, "N": n, "K": k,
            "custom_ms": custom_ms, "cublas_ms": cublas_ms,
            "custom_gflops": 2.0 * m * n * k / (custom_ms * 1e6),
            "cublas_gflops": 2.0 * m * n * k / (cublas_ms * 1e6),
            "custom_max_abs_err": max_absolute,
            "custom_speedup": speedup, "correctness_check": "PASS",
            "performance_check": "PASS" if speedup > PERFORMANCE_THRESHOLD else "FAIL"}


def benchmark_shape(gpu, shape, options):
    m, n, k = shape
    free, total = SIZE(), SIZE()
    gpu.call("cuMemGetInfo_v2", ct.byref(free), ct.byref(total))
    required = 4 * (m * k + k * n + 2 * m * n)
    if required > free.value:
        raise RuntimeError(f"{shape} requires {required / 2**20:.1f} MiB for matrices; "
                           f"only {free.value / 2**20:.1f} MiB is free.")
    rng = random.Random(options.seed)
    a = array("f", (rng.uniform(-1.0, 1.0) for _ in range(m * k)))
    b = array("f", (rng.uniform(-1.0, 1.0) for _ in range(k * n)))
    try:
        da, db = gpu.allocate(m * k), gpu.allocate(k * n)
        dc, dr = gpu.allocate(m * n), gpu.allocate(m * n)
        gpu.upload(da, a)
        gpu.upload(db, b)
        blas_launch = gpu.cublas_launcher(da, db, dr, m, n, k)
        gpu.poison(dr, m * n)
        blas_launch()
        gpu.synchronize()
        reference = gpu.download(dr, m * n)
        launch = gpu.kernel_launcher(da, db, dc, m, n, k)
        gpu.poison(dc, m * n)
        launch()
        gpu.synchronize()
        output = gpu.download(dc, m * n)
        failures, max_absolute, max_scaled = verify(output, reference,
                                                    options.atol, options.rtol)
        if failures:
            raise RuntimeError(f"Custom kernel validation failed at {shape}: {failures} values; "
                               f"max abs error={max_absolute:.6g}, "
                               f"max error/tolerance={max_scaled:.6g}")
        outputs = {"cublas": reference, "custom": output}
        launchers = {"cublas": blas_launch, "custom": launch}
        verify_cpu(outputs, a, b, m, n, k, options.cpu_samples,
                   options.atol, options.rtol, options.seed + 1)
        samples = measure(gpu, launchers, options.iterations, options.repeats,
                          options.warmup, options.timing)
        return summarize_results(shape, samples, max_absolute)
    finally:
        gpu.synchronize()
        gpu.free_allocations()


def positive_int(text):
    value = int(text)
    if not 1 <= value <= 2**31 - 1:
        raise argparse.ArgumentTypeError("must be between 1 and INT_MAX")
    return value


def nonnegative_int(text):
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return value


def positive_float(text):
    value = float(text)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("must be finite and positive")
    return value


def parse_shape(text):
    try:
        dimensions = tuple(positive_int(part) for part in text.lower().replace("x", ",").split(","))
        if len(dimensions) != 3:
            raise ValueError()
        return dimensions
    except (ValueError, argparse.ArgumentTypeError):
        raise argparse.ArgumentTypeError("shape must be M,N,K or MxNxK, with positive dimensions")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--sizes", nargs="+", type=positive_int,
                        help="square matrix sizes; replaces the default shape suite")
    parser.add_argument("--shape", action="append", type=parse_shape,
                        help="M,N,K (repeatable); used with --sizes, or by itself")
    parser.add_argument("--timing", choices=("graph", "launch"), default="graph",
                        help="graph replay avoids Python submission gaps; launch measures direct calls")
    parser.add_argument("--iterations", type=positive_int, default=100,
                        help="launches per timed batch")
    parser.add_argument("--repeats", type=positive_int, default=5,
                        help="timed batches; report their median")
    parser.add_argument("--warmup", type=nonnegative_int, default=10)
    parser.add_argument("--cpu-samples", type=nonnegative_int, default=32,
                        help="independent FP64 CPU dot products per shape; 0 disables")
    parser.add_argument("--atol", type=positive_float, default=1e-3)
    parser.add_argument("--rtol", type=positive_float, default=1e-3)
    parser.add_argument("--device", type=nonnegative_int, default=0)
    parser.add_argument("--seed", type=int, default=2026)
    return parser.parse_args()


def main():
    options = parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        try:
            (PASS_SYMBOL + FAIL_SYMBOL).encode(sys.stdout.encoding or "utf-8")
        except UnicodeEncodeError:
            sys.stdout.reconfigure(encoding="utf-8")
    if array("f").itemsize != 4 or ct.sizeof(PTR) != 8:
        raise RuntimeError("A 64-bit Python build with 32-bit array('f') is required.")
    shapes = [(size, size, size) for size in options.sizes or []]
    shapes.extend(options.shape or [])
    shapes = list(dict.fromkeys(shapes or DEFAULT_SHAPES))
    table = ConsoleTable(shapes)
    gpu = Gpu(CudaLibraries(), options.device)
    try:
        source = Path(__file__).with_name("sgemm_kernels.cu").read_text(encoding="utf-8")
        gpu.compile(source)
        table.header()
        correctness_passed = performance_passed = both_passed = 0
        for shape in shapes:
            row = benchmark_shape(gpu, shape, options)
            table.row(row)
            correct = row["correctness_check"] == "PASS"
            fast = row["performance_check"] == "PASS"
            correctness_passed += correct
            performance_passed += fast
            both_passed += correct and fast
        total = len(shapes)
        print(f"\nSummary: {total} cases, {2 * total} checks")
        print(f"Passed: Corr {correctness_passed}/{total} | "
              f"Perf {performance_passed}/{total} | Both {both_passed}/{total}")
        return 0
    finally:
        gpu.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, OSError, MemoryError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
