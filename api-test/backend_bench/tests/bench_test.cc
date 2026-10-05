// backend_bench 测试套件。
//
// 每条断言只描述**期望的行为**，不解释实现为什么没做到。失败时会打印实际的
// 输出，方便定位。
//
// 计分：三个分项各占 1 分，满分 3 分。三项互相独立，修好一部分就拿到对应的分。
#include <iostream>
#include <string>
#include <vector>

#include "bench/service.h"
#include "check.h"

using bench::Service;
using check::Equal;
using check::Report;

namespace {

std::string Run(Service& service, const std::string& line) {
    return service.Execute(line);
}

// ---- 分项 1：分页 -----------------------------------------------------------
bool CheckPaging() {
    int before = check::g_failures;
    Service service;
    Run(service, "load 10");
    Equal("P1 page(0,4) 返回最前面的四条记录",
          Run(service, "page 0 4"), "job-001 job-002 job-003 job-004");
    Equal("P2 page(4,4) 返回接下来的四条记录",
          Run(service, "page 4 4"), "job-005 job-006 job-007 job-008");
    Equal("P3 表末尾的记录可以被取到",
          Run(service, "page 8 4"), "job-009 job-010");
    Equal("P4 单条记录的分页",
          Run(service, "page 6 1"), "job-007");
    Equal("P5 逐页遍历能恰好访问每条记录一次",
          Run(service, "page 0 10"),
          "job-001 job-002 job-003 job-004 job-005 job-006 job-007 job-008 job-009 job-010");
    return check::g_failures == before;
}

// ---- 分项 2：统计 -----------------------------------------------------------
bool CheckStatistics() {
    int before = check::g_failures;
    Service service;
    Run(service, "reset");
    Run(service, "load 2");  // cost 为 1, 2
    Equal("S1 第一批的统计数字正确",
          Run(service, "stats"), "count=2 total=3 mean=2");
    Run(service, "load 3");  // cost 为 1, 2, 3
    Equal("S2 第二批在前一批的基础上累加",
          Run(service, "stats"), "count=5 total=9 mean=2");
    Run(service, "load 6");  // cost 为 1, 2, 3, 4, 5, 6
    Equal("S3 第三批继续累加",
          Run(service, "stats"), "count=11 total=30 mean=3");
    Equal("S4 反复查询不会改变统计数字",
          Run(service, "stats"), "count=11 total=30 mean=3");
    return check::g_failures == before;
}

// ---- 分项 3：线程池 ---------------------------------------------------------
bool CheckWorkerPool() {
    int before = check::g_failures;
    Service service;
    bool all_exact = true;
    for (int round = 0; round < 5; ++round) {
        if (Run(service, "run 200") != "ran 200/200") all_exact = false;
    }
    Report(all_exact, "W1 提交的任务全部被报告为已完成",
           "报告的数量少于提交的数量");

    bool large_exact = true;
    for (int round = 0; round < 3; ++round) {
        if (Run(service, "run 800") != "ran 800/800") large_exact = false;
    }
    Report(large_exact, "W2 更大批量的任务也全部入账",
           "报告的数量少于提交的数量");
    return check::g_failures == before;
}

}  // namespace

int main() {
    std::cout << "== backend_bench ==\n";
    bool paging = CheckPaging();
    bool stats = CheckStatistics();
    bool pool = CheckWorkerPool();

    std::cout << "\n-- 分项结果 --\n";
    std::cout << (paging ? "[PASS]" : "[FAIL]") << " 1 分页\n";
    std::cout << (stats ? "[PASS]" : "[FAIL]") << " 2 统计\n";
    std::cout << (pool ? "[PASS]" : "[FAIL]") << " 3 线程池\n";
    int score = (paging ? 1 : 0) + (stats ? 1 : 0) + (pool ? 1 : 0);
    std::cout << "\nscore = " << score << "/3\n";

    check::Summary("backend_bench");
    return score;
}
