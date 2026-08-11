cmake_minimum_required(VERSION 3.22.1)
project(psyai_sc VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Optimization flags for audio
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fno-exceptions -fno-rtti -O3 -ffast-math")

# NEON on ARM64
if(ANDROID_ABI STREQUAL "arm64-v8a")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -march=armv8-a+simd")
endif()

# ============================================================================
# Dependencies
# ============================================================================

# Oboe (Google's audio library)
include(FetchContent)
FetchContent_Declare(
    oboe
    GIT_REPOSITORY https://github.com/google/oboe.git
    GIT_TAG 1.8.0
)
FetchContent_MakeAvailable(oboe)

# SuperCollider (if building from source)
# For now, we assume scsynth is pre-built and linked
# set(SC_PATH ${CMAKE_SOURCE_DIR}/libs/supercollider)
# add_subdirectory(${SC_PATH})

# ============================================================================
# Library
# ============================================================================

add_library(psyai_sc SHARED
    sc_jni.cpp
)

target_include_directories(psyai_sc PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    # ${SC_PATH}/include  # SuperCollider headers
)

target_link_libraries(psyai_sc
    oboe
    android
    log
)

# If linking pre-built scsynth
# target_link_libraries(psyai_sc ${SC_PATH}/libs/${ANDROID_ABI}/libscsynth.so)

# ============================================================================
# Compiler warnings
# ============================================================================

target_compile_options(psyai_sc PRIVATE
    -Wall
    -Wextra
    -Wpedantic
    -Wno-unused-parameter  # JNI has many unused env params
)
