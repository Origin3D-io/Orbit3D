cmake_minimum_required(VERSION 3.20)
project(OrbitHub VERSION 0.2.1 LANGUAGES C CXX)

# The portable broker must not depend on an installed Visual C++ runtime.
if(MSVC)
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Threads REQUIRED)

add_library(orbit3d_wire STATIC src/wire.cpp)
target_include_directories(orbit3d_wire PUBLIC include)
target_compile_options(orbit3d_wire PRIVATE
    $<$<CXX_COMPILER_ID:AppleClang,Clang,GNU>:-Wall;-Wextra;-Wpedantic;-Werror>)

add_library(orbit3d_sdk STATIC src/sdk.cpp)
target_compile_definitions(orbit3d_sdk PUBLIC ORBIT3D_STATIC)
target_include_directories(orbit3d_sdk PUBLIC include PRIVATE src)
target_link_libraries(orbit3d_sdk PUBLIC orbit3d_wire Threads::Threads)

add_library(orbit3d_adapters STATIC
    src/adapter.cpp
    src/simulator_adapter.cpp)
target_include_directories(orbit3d_adapters PUBLIC include PRIVATE src)
target_link_libraries(orbit3d_adapters PUBLIC orbit3d_wire Threads::Threads)

add_executable(orbithub src/main.cpp src/server.cpp)
target_compile_definitions(orbithub PRIVATE ORBIT_HUB_VERSION="${PROJECT_VERSION}")
target_include_directories(orbithub PRIVATE include src)
target_link_libraries(orbithub PRIVATE orbit3d_adapters Threads::Threads)

add_executable(orbit3d_sdk_smoke tests/sdk_smoke.cpp)
target_link_libraries(orbit3d_sdk_smoke PRIVATE orbit3d_sdk)

add_executable(orbit3d_c_sdk_smoke tests/c_sdk_smoke.c)
set_target_properties(orbit3d_c_sdk_smoke PROPERTIES LINKER_LANGUAGE CXX)
target_link_libraries(orbit3d_c_sdk_smoke PRIVATE orbit3d_sdk)

if(WIN32)
    target_link_libraries(orbit3d_sdk PRIVATE ws2_32)
    target_link_libraries(orbithub PRIVATE ws2_32)
endif()

enable_testing()
add_executable(orbit3d_sdk_deadline_test tests/sdk_deadline_test.cpp)
target_include_directories(orbit3d_sdk_deadline_test PRIVATE src)
target_link_libraries(orbit3d_sdk_deadline_test PRIVATE orbit3d_sdk)
add_test(NAME orbit3d_sdk_deadline_test COMMAND orbit3d_sdk_deadline_test)
set_tests_properties(orbit3d_sdk_deadline_test PROPERTIES TIMEOUT 5)
add_executable(orbit3d_wire_test tests/wire_test.cpp)
target_link_libraries(orbit3d_wire_test PRIVATE orbit3d_wire)
add_test(NAME orbit3d_wire_test COMMAND orbit3d_wire_test)

find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_test(NAME orbit3d_integration
    COMMAND ${Python3_EXECUTABLE} -m unittest discover -s ${CMAKE_CURRENT_SOURCE_DIR}/tests -p "test_*.py" -v)
set_tests_properties(orbit3d_integration PROPERTIES
    ENVIRONMENT "ORBIT_HUB_TEST_BIN_DIR=$<TARGET_FILE_DIR:orbithub>;PYTHONPATH=${CMAKE_CURRENT_SOURCE_DIR}/sdk/python/src"
    TIMEOUT 60)
