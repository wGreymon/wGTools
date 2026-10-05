#pragma once

#include <condition_variable>
#include <cstddef>
#include <mutex>
#include <queue>
#include <thread>
#include <vector>

#include "bench/types.h"

namespace bench {

// A fixed-size worker pool.  `Run` drains a batch of jobs and reports how many
// completed; the pool survives between calls and is only torn down in the
// destructor.
class ThreadPool {
public:
    explicit ThreadPool(int workers);
    ~ThreadPool();

    ThreadPool(const ThreadPool&) = delete;
    ThreadPool& operator=(const ThreadPool&) = delete;

    // Subscribes a batch and blocks until every job in it has run.  Returns
    // how many jobs from *this* batch finished.
    std::size_t Run(const std::vector<Job>& jobs);

    int Workers() const { return workers_; }

private:
    void WorkerLoop();

    std::mutex mutex_;
    std::condition_variable ready_;
    std::condition_variable idle_;
    std::queue<Job> queue_;
    std::vector<std::thread> threads_;
    std::size_t pending_ = 0;    // jobs queued but not yet finished
    std::size_t finished_ = 0;   // jobs from the current batch that finished
    bool stopping_ = false;
    int workers_ = 0;
};

}  // namespace bench
