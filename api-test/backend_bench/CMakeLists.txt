cmake_minimum_required(VERSION 3.16)
project(backend_bench CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

add_compile_options(-Wall -Wextra)

add_library(bench_core STATIC
  src/parser.cpp
  src/store.cpp
  src/stats.cpp
  src/pool.cpp
  src/service.cpp
)
target_include_directories(bench_core PUBLIC include)
# Tests include "check.h" from tests/, so the project root must be on the path.
target_include_directories(bench_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

find_package(Threads REQUIRED)
target_link_libraries(bench_core PUBLIC Threads::Threads)

add_executable(service src/main.cpp)
target_link_libraries(service PRIVATE bench_core)

add_executable(bench_test tests/bench_test.cc)
target_link_libraries(bench_test PRIVATE bench_core)

enable_testing()
add_test(NAME bench COMMAND bench_test)
