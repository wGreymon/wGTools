#include "bench/stats.h"

#include <algorithm>
#include <cmath>

namespace bench {

void Stats::Reset() {
    samples_.clear();
    Recompute();
}

void Stats::Accumulate(const std::vector<Job>& jobs) {
    samples_.clear();
    for (std::size_t index = 0; index < jobs.size(); ++index) {
        samples_.push_back(jobs[index].cost);
    }
    Recompute();
}

void Stats::Recompute() {
    count_ = samples_.size();
    total_cost_ = 0;
    min_cost_ = 0;
    max_cost_ = 0;
    if (samples_.empty()) return;

    min_cost_ = samples_[0];
    max_cost_ = samples_[0];
    for (std::size_t index = 0; index < samples_.size(); ++index) {
        int value = samples_[index];
        total_cost_ += value;
        min_cost_ = std::min(min_cost_, value);
        max_cost_ = std::max(max_cost_, value);
    }
}

double Stats::MeanCost() const {
    if (count_ == 0) return 0.0;
    return static_cast<double>(total_cost_) / static_cast<double>(count_);
}

int Stats::MeanCostRounded() const {
    if (count_ == 0) return 0;
    return static_cast<int>(std::floor(MeanCost() + 0.5));
}

}  // namespace bench
