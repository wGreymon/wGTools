#pragma once

#include <string>
#include <vector>

#include "bench/types.h"

namespace bench {

// Parses one command line of the form "<verb> <argument>", e.g.
//   "tag alpha"     -> {"tag", "alpha"}
//   "run 12"        -> {"run", "12"}
// Malformed lines are rejected instead of silently producing an empty token.
class Parser {
public:
    struct Result {
        bool ok = false;
        std::string verb;
        std::string value;   // the argument text, spaces preserved
        std::string error;
    };

    static bool IsSpace(char c);
    static std::string Trim(const std::string& text);

    // Splits `line` into a verb and the remaining argument text.
    static Result Parse(const std::string& line);

    // Extracts the argument from a line that is known to be well formed.
    // Returns the text after the first space, with surrounding spaces trimmed.
    static std::string ArgumentText(const std::string& line);

    // Parses an integer argument, rejecting trailing garbage, overflow and
    // an empty string.  Returns false and sets `error` on failure.
    static bool ParseInt(const std::string& text, int& out, std::string& error);

    // Splits a comma separated list, trimming each element and dropping empties.
    static std::vector<std::string> SplitList(const std::string& text);
};

}  // namespace bench
