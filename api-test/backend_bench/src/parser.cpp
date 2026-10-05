#include "bench/parser.h"

#include <cerrno>
#include <climits>
#include <cstdlib>

namespace bench {

bool Parser::IsSpace(char c) {
    return c == ' ' || c == '\t' || c == '\r' || c == '\n' || c == '\v' || c == '\f';
}

std::string Parser::Trim(const std::string& text) {
    std::size_t begin = 0;
    std::size_t end = text.size();
    while (begin < end && IsSpace(text[begin])) ++begin;
    while (end > begin && IsSpace(text[end - 1])) --end;
    return text.substr(begin, end - begin);
}

std::string Parser::ArgumentText(const std::string& line) {
    std::size_t space = line.find(' ');
    if (space == std::string::npos) return std::string();
    return Trim(line.substr(space + 1));
}

Parser::Result Parser::Parse(const std::string& line) {
    Result result;
    std::string trimmed = Trim(line);
    if (trimmed.empty()) {
        result.error = "empty input";
        return result;
    }
    std::size_t space = trimmed.find(' ');
    result.verb = space == std::string::npos ? trimmed : trimmed.substr(0, space);
    result.value = space == std::string::npos ? std::string() : Trim(trimmed.substr(space + 1));
    result.ok = true;
    return result;
}

bool Parser::ParseInt(const std::string& text, int& out, std::string& error) {
    std::string trimmed = Trim(text);
    if (trimmed.empty()) {
        error = "expected an integer, got an empty value";
        return false;
    }
    errno = 0;
    char* end = nullptr;
    long value = std::strtol(trimmed.c_str(), &end, 10);
    if (end == trimmed.c_str() || *end != '\0') {
        error = "expected an integer, got '" + trimmed + "'";
        return false;
    }
    if (errno == ERANGE || value > INT_MAX || value < INT_MIN) {
        error = "integer out of range: '" + trimmed + "'";
        return false;
    }
    out = static_cast<int>(value);
    return true;
}

std::vector<std::string> Parser::SplitList(const std::string& text) {
    std::vector<std::string> items;
    std::size_t start = 0;
    while (start <= text.size()) {
        std::size_t comma = text.find(',', start);
        std::string piece = comma == std::string::npos
                                ? text.substr(start)
                                : text.substr(start, comma - start);
        std::string item = Trim(piece);
        if (!item.empty()) items.push_back(item);
        if (comma == std::string::npos) break;
        start = comma + 1;
    }
    return items;
}

}  // namespace bench
