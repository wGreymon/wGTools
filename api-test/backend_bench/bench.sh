#!/bin/bash
# backend_bench 一键测试。
#
#   ./bench.sh              编译并运行测试，打印 score = N/3
#   ./bench.sh --verbose    额外打印每条断言的通过情况
#
# 编译当前 src/ 下的实现，跑 tests/bench_test.cc，按通过的分项计分。
# 三个分项互相独立，各占 1 分。
#
# 退出码：3 分返回 0，未满分返回 1，编译失败或测试文件被改动返回 2。
set -u

HERE=$(cd "$(dirname "$0")" && pwd)

VERBOSE=0
case "${1:-}" in
    --verbose|-v) VERBOSE=1 ;;
    "") ;;
    *) echo "用法: $0 [--verbose]" >&2; exit 2 ;;
esac

TEST="$HERE/tests/bench_test.cc"
CHECK="$HERE/tests/check.h"
[ -f "$TEST" ] || { echo "找不到测试文件: $TEST" >&2; exit 2; }

# 测试文件是评分口径本身，不属于可改动范围。被改过就不再产生分数，否则改测试
# 就能改成满分——那样量到的不是实现，是测试。
EXPECT_TEST=6dd2bd8488bbce4c728bcd4f058ec65c80990bbab7cd808273e06b9ec98ebd92
EXPECT_CHECK=d0c1bcee2a3f25e3ea318690b44bb7490a93e50bcee255a05dd4134dce3a0da8
# 先把 CR 剔掉再算哈希：文件本身是 LF，但经过 Windows 的 git（autocrlf）或某些
# 编辑器转手后可能变成 CRLF。行尾不同不该改变分数，否则收方会永远拿到 invalid。
digest() { tr -d '\r' < "$1" 2>/dev/null | sha256sum | cut -d' ' -f1; }
if [ "$(digest "$TEST")" != "$EXPECT_TEST" ] || [ "$(digest "$CHECK")" != "$EXPECT_CHECK" ]; then
    echo "score = invalid" >&2
    echo "tests/ 下的测试文件已被修改。测试文件是评分口径，请在原始副本上重新评测。" >&2
    exit 2
fi

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# 显式列出源文件：src/main.cpp 也定义了 main，会和测试的入口点冲突。
SRC="$HERE/src"
g++ -std=c++17 -O1 -I"$HERE/include" -I"$HERE" -pthread \
    "$TEST" \
    "$SRC/parser.cpp" "$SRC/store.cpp" "$SRC/stats.cpp" \
    "$SRC/pool.cpp" "$SRC/service.cpp" \
    -o "$WORK/bench_test" 2>"$WORK/build.err"

if [ ! -x "$WORK/bench_test" ]; then
    echo "编译失败:" >&2
    head -20 "$WORK/build.err" >&2
    exit 2
fi

RESULT=$("$WORK/bench_test" 2>&1)
SCORE=$(printf '%s\n' "$RESULT" | sed -n 's/^score = \([0-9]\)\/3$/\1/p')

if [ "$VERBOSE" -eq 1 ]; then
    printf '%s\n' "$RESULT"
else
    echo "score = ${SCORE:-?}/3"
fi

# 只有满分才算通过。（不能直接把分数当退出码：0/3 会被当成成功。）
if [ "${SCORE:-}" = "3" ]; then
    exit 0
fi
exit 1
