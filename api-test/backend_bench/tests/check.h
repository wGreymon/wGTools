#pragma once

#include <iostream>
#include <string>

namespace check {

inline int g_checks = 0;
inline int g_failures = 0;

// 记录一条断言。`detail` 用于描述观察到的现象，失败时打印出来。
inline void Report(bool ok, const std::string& name, const std::string& detail = "") {
    ++g_checks;
    if (ok) {
        std::cout << "[PASS] " << name << "\n";
        return;
    }
    ++g_failures;
    std::cout << "[FAIL] " << name << "\n";
    if (!detail.empty()) std::cout << "       " << detail << "\n";
}

inline bool Equal(const std::string& name, const std::string& got,
                  const std::string& expected) {
    bool ok = got == expected;
    Report(ok, name, ok ? "" : "expected \"" + expected + "\", got \"" + got + "\"");
    return ok;
}

inline int Summary(const std::string& label) {
    std::cout << label << ": " << (g_checks - g_failures) << "/" << g_checks
              << " checks passed\n";
    return g_failures == 0 ? 0 : 1;
}

}  // namespace check
