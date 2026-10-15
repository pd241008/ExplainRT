cmake_minimum_required(VERSION 3.24)
project(gate LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Scaffold placeholder for the C++ gate stage.
# Real dependencies (protobuf C++ runtime, JSON, JSON-schema, libseccomp) are
# pinned when G1 starts, not here.
add_executable(gate_stub include/broker.h src/main.cpp)
