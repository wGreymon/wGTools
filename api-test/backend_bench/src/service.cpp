#include "bench/service.h"

#include <cstdio>
#include <sstream>

namespace bench {
namespace {

const int kDefaultWorkers = 8;

// Formats a size_t / long long as a decimal string without locale surprises.
std::string ToText(long long value) {
    std::ostringstream out;
    out << value;
    return out.str();
}

}  // namespace

Service::Service() : pool_(kDefaultWorkers) {}

Service::~Service() = default;

std::string Service::Execute(const std::string& line) {
    Parser::Result parsed = Parser::Parse(line);
    if (!parsed.ok) return "error: " + parsed.error;

    const std::string& verb = parsed.verb;
    const std::string& value = parsed.value;

    if (verb == "load") return CommandLoad(value);
    if (verb == "add") return CommandAdd(value);
    if (verb == "page") return CommandPage(value);
    if (verb == "run") return CommandRun(value);
    if (verb == "stats") return CommandStats(value);
    if (verb == "reset") return CommandReset(value);
    if (verb == "help") return CommandHelp(value);
    return "error: unknown command '" + verb + "'";
}

std::string Service::CommandLoad(const std::string& argument) {
    int count = 0;
    std::string error;
    if (!Parser::ParseInt(argument, count, error)) return "error: " + error;
    if (count < 0) return "error: count must not be negative";
    store_.LoadSynthetic(count);
    stats_.Accumulate(store_.All());
    return "loaded " + ToText(store_.Size());
}

std::string Service::CommandAdd(const std::string& argument) {
    std::vector<std::string> items = Parser::SplitList(argument);
    if (items.size() != 2) return "error: expected '<name> <cost>'";
    int cost = 0;
    std::string error;
    if (!Parser::ParseInt(items[1], cost, error)) return "error: " + error;
    if (cost <= 0) return "error: cost must be positive";
    store_.Add(items[0], cost);
    stats_.Accumulate(store_.All());
    return "added " + items[0];
}

std::string Service::CommandPage(const std::string& argument) {
    // Accept "<offset> <limit>".
    std::vector<std::string> items;
    std::size_t start = 0;
    while (start <= argument.size()) {
        std::size_t space = argument.find(' ', start);
        std::string piece = space == std::string::npos
                                ? argument.substr(start)
                                : argument.substr(start, space - start);
        std::string trimmed = Parser::Trim(piece);
        if (!trimmed.empty()) items.push_back(trimmed);
        if (space == std::string::npos) break;
        start = space + 1;
    }
    if (items.size() != 2) return "error: expected '<offset> <limit>'";

    int offset = 0, limit = 0;
    std::string error;
    if (!Parser::ParseInt(items[0], offset, error)) return "error: " + error;
    if (!Parser::ParseInt(items[1], limit, error)) return "error: " + error;
    if (offset < 0 || limit < 0) return "error: offset and limit must not be negative";

    std::vector<Job> page = store_.Page(static_cast<std::size_t>(offset),
                                        static_cast<std::size_t>(limit));
    std::string result;
    for (std::size_t index = 0; index < page.size(); ++index) {
        if (index) result += ' ';
        result += page[index].name;
    }
    return result.empty() ? "empty" : result;
}

std::string Service::CommandRun(const std::string& argument) {
    int count = 0;
    std::string error;
    if (!Parser::ParseInt(argument, count, error)) return "error: " + error;
    if (count < 0) return "error: count must not be negative";

    std::vector<Job> batch;
    batch.reserve(static_cast<std::size_t>(count));
    for (int index = 0; index < count; ++index) {
        Job job;
        job.id = index;
        job.name = "batch-job";
        job.cost = 1;
        batch.push_back(job);
    }
    std::size_t ran = pool_.Run(batch);
    return "ran " + ToText(static_cast<long long>(ran)) + "/" + ToText(count);
}

std::string Service::CommandStats(const std::string&) {
    // Records are folded in as they arrive, so this is a pure report and can be
    // called repeatedly without changing the totals.
    return "count=" + ToText(static_cast<long long>(stats_.Count())) +
           " total=" + ToText(stats_.TotalCost()) +
           " mean=" + ToText(stats_.MeanCostRounded());
}

std::string Service::CommandReset(const std::string&) {
    store_.Clear();
    stats_.Reset();
    return "reset";
}

std::string Service::CommandHelp(const std::string&) {
    return "load <count> | add <name> <cost> | page <offset> <limit> | "
           "run <count> | stats | reset | help";
}

}  // namespace bench
