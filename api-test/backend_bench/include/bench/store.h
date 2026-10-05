#pragma once

#include <cstddef>
#include <string>
#include <vector>

#include "bench/types.h"

namespace bench {

// In-memory record table with offset/limit access, the shape a list endpoint
// takes.  Records are numbered from 1 in insertion order.
class RecordStore {
public:
    void Add(const std::string& name, int cost);

    // Replaces the table with `count` synthetic records.
    void LoadSynthetic(int count);

    std::size_t Size() const { return records_.size(); }
    const std::vector<Job>& All() const { return records_; }

    // Returns the records in [offset, offset + limit).  A limit of zero, or an
    // offset at or past the end, yields an empty page.
    std::vector<Job> Page(std::size_t offset, std::size_t limit) const;

    void Clear();

private:
    std::vector<Job> records_;
    int next_id_ = 1;
};

}  // namespace bench
