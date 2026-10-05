#include "bench/store.h"

#include <cstdio>

namespace bench {

void RecordStore::Add(const std::string& name, int cost) {
    Job job;
    job.id = next_id_++;
    job.name = name;
    job.cost = cost;
    records_.push_back(job);
}

void RecordStore::LoadSynthetic(int count) {
    Clear();
    char buffer[32];
    for (int index = 0; index < count; ++index) {
        std::snprintf(buffer, sizeof(buffer), "job-%03d", index + 1);
        // Deterministic cost so two benchmark runs stay comparable.
        Add(buffer, 1 + (index % 7));
    }
}

std::vector<Job> RecordStore::Page(std::size_t offset, std::size_t limit) const {
    std::vector<Job> page;
    if (limit == 0 || offset > records_.size()) return page;

    // Clamp the window to the end of the table so the final page may be short.
    std::size_t end = offset + limit;
    if (end > records_.size()) end = records_.size();
    for (std::size_t index = offset + 1; index < end; ++index) {
        page.push_back(records_[index]);
    }
    return page;
}

void RecordStore::Clear() {
    records_.clear();
    next_id_ = 1;
}

}  // namespace bench
