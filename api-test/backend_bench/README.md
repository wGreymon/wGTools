# backend_bench — C++ 后端调试任务

一个常驻的内存服务（模拟后端），从 stdin 逐行读命令，逐行输出结果。

## 规则

- 可以修改 `src/`、`include/`、`CMakeLists.txt`。
- **不要修改 `tests/`**。那是评分口径本身。`bench.sh` 会校验它的哈希，改动后
  直接拒绝出分，而不是给出一个可以刷的分。
- 不要修改 `bench.sh`。即使改了，评分也只在原始副本上进行。

## 服务规格

```
load <count>            用 <count> 条合成记录替换表
                        记录名 job-001..job-<count>，cost = 1 + (index % 7)
add <name> <cost>       追加一条记录（cost 必须为正）
page <offset> <limit>   打印 [offset, offset + limit) 内的记录名，空格分隔
                        空页输出 empty；limit 为 0 或 offset 越界时为空页
run <count>             提交 <count> 个任务，打印 "ran <完成数>/<count>"
stats                   打印 "count=<n> total=<n> mean=<n>"
                        mean 为四舍五入后的整数
reset                   清空表和统计
help                    列出命令
quit / exit             退出
```

关键结构：`RecordStore`、`Stats`、`ThreadPool` 都是**服务启动时创建一次、整个生命
周期复用**——真实后端就是这个形态。

## 构建与运行

```bash
cmake -S . -B build && cmake --build build -j4
printf 'load 10\npage 0 3\nstats\nrun 200\n' | ./build/service
```

## 测试

```bash
./bench.sh              # 只打印分数，如 score = 2/3
./bench.sh --verbose    # 再打印每条断言的通过情况
```

计分：三个分项**互相独立**，各占 1 分，满分 3 分。只有整块断言全过才拿到该分，
所以总分是 0/1/2/3 四档。修好一部分就拿到对应的分。

退出码：`0` 满分，`1` 未满分，`2` 编译失败或测试文件被改动。

也可以走 CMake：

```bash
cmake -S . -B build && cmake --build build -j4 && ./build/bench_test
```
