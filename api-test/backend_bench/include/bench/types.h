#pragma once

#include <string>

namespace bench {

// A unit of work submitted to the pool.
struct Job {
    int id = 0;
    std::string name;
    int cost = 1;  // relative work units; also sampled into Stats
};

}  // namespace bench
