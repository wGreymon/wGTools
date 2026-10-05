#include <iostream>
#include <string>

#include "bench/service.h"

// Reads commands from stdin, one per line, and prints one response per line.
// Used both interactively and by the end-to-end test.
int main(int argc, char** argv) {
    bool echo_prompt = argc > 1 && std::string(argv[1]) == "--prompt";
    bench::Service service;
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;
        if (line == "quit" || line == "exit") break;
        if (echo_prompt) std::cout << "> ";
        std::cout << service.Execute(line) << std::endl;
    }
    return 0;
}
