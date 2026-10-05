#pragma once

#include <cstddef>
#include <string>
#include <vector>

#include "bench/types.h"

namespace bench {

// Running statistics over submitted jobs.  A Stats object is created once per
// service instance and accumulates across every batch it is handed.  All
// reported figures are derived from the retained sample list.
class Stats {
public:
    void Reset();

    // Folds one batch of jobs into the running totals.
    void Accumulate(const std::vector<Job>& jobs);

    std::size_t Count() const { return count_; }
    long long TotalCost() const { return total_cost_; }
    int MinCost() const { return count_ ? min_cost_ : 0; }
    int MaxCost() const { return count_ ? max_cost_ : 0; }
    double MeanCost() const;

    // Mean cost rounded to the nearest integer, as an integer endpoint would
    // report it.
    int MeanCostRounded() const;

private:
    // Recomputes the summaries from the retained samples.
    void Recompute();

    std::vector<int> samples_;
    std::size_t count_ = 0;
    long long total_cost_ = 0;
    int min_cost_ = 0;
    int max_cost_ = 0;
};

}  // namespace bench
