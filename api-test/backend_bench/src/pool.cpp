#include "bench/pool.h"

namespace bench {

ThreadPool::ThreadPool(int workers) : workers_(workers < 1 ? 1 : workers) {
    threads_.reserve(static_cast<std::size_t>(workers_));
    for (int index = 0; index < workers_; ++index) {
        threads_.emplace_back([this] { WorkerLoop(); });
    }
}

ThreadPool::~ThreadPool() {
    {
        std::lock_guard<std::mutex> lock(mutex_);
        stopping_ = true;
    }
    ready_.notify_all();
    for (std::thread& thread : threads_) {
        if (thread.joinable()) thread.join();
    }
}

void ThreadPool::WorkerLoop() {
    for (;;) {
        Job job;
        {
            std::unique_lock<std::mutex> lock(mutex_);
            ready_.wait(lock, [this] { return stopping_ || !queue_.empty(); });
            if (queue_.empty()) {
                if (stopping_) return;
                continue;
            }
            job = queue_.front();
            queue_.pop();
        }

        // Stand-in for real work, with a deterministic cost.
        volatile long long sink = 0;
        for (int step = 0; step < job.cost * 400; ++step) sink += step;
        (void)sink;

        // Tally the finished job.
        ++finished_;

        // Release the slot it occupied.
        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (pending_ > 0) --pending_;
        }
        idle_.notify_all();
    }
}

std::size_t ThreadPool::Run(const std::vector<Job>& jobs) {
    {
        std::lock_guard<std::mutex> lock(mutex_);
        for (const Job& job : jobs) queue_.push(job);
        pending_ += jobs.size();
        finished_ = 0;
    }
    ready_.notify_all();

    std::unique_lock<std::mutex> lock(mutex_);
    idle_.wait(lock, [this] { return pending_ == 0; });
    return finished_;
}

}  // namespace bench
