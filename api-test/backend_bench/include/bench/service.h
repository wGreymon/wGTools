#pragma once

#include <string>
#include <vector>

#include "bench/parser.h"
#include "bench/pool.h"
#include "bench/stats.h"
#include "bench/store.h"

namespace bench {

// The service under test.  It keeps one RecordStore, one Stats and one
// ThreadPool for its whole lifetime, the way a long-running daemon would.
// Registered commands:
//
//   load <count>          replace the table with <count> synthetic records
//   add <name> <cost>     append one record
//   page <offset> <limit> print the page's record names, space separated
//   run <count>           submit <count> synthetic jobs, print how many ran
//   stats                 print "count=<n> total=<n> mean=<n>"
//   reset                 clear the table and the statistics
//   help                  list the commands
class Service {
public:
    Service();
    ~Service();

    // Executes one command line.  Returns the text to report to the caller.
    std::string Execute(const std::string& line);

    RecordStore& Store() { return store_; }
    Stats& Statistics() { return stats_; }

private:
    std::string CommandLoad(const std::string& argument);
    std::string CommandAdd(const std::string& argument);
    std::string CommandPage(const std::string& argument);
    std::string CommandRun(const std::string& argument);
    std::string CommandStats(const std::string& argument);
    std::string CommandReset(const std::string& argument);
    std::string CommandHelp(const std::string& argument);

    RecordStore store_;
    Stats stats_;
    ThreadPool pool_;
};

}  // namespace bench
