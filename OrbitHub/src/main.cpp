#include "adapter.hpp"
#include "orbit3d/wire.hpp"
#include "simulator_adapter.hpp"

#include <atomic>
#include <charconv>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <string>

#include <csignal>
#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#endif

#ifndef ORBIT_HUB_VERSION
#define ORBIT_HUB_VERSION "0.2.1"
#endif

namespace {
volatile std::sig_atomic_t interrupted = 0;
void on_signal(int) {
    interrupted = 1;
}
#if defined(_WIN32)
std::atomic<bool> console_stopped{false};
BOOL WINAPI on_console_event(DWORD event) {
    if (event != CTRL_C_EVENT && event != CTRL_BREAK_EVENT)
        return FALSE;
    console_stopped.store(true);
    return TRUE;
}
#endif
bool shutdown_requested() {
#if defined(_WIN32)
    if (console_stopped.load())
        return true;
#endif
    return interrupted != 0;
}
} // namespace

namespace orbit3d::hub {
int run_server(std::uint16_t port, std::unique_ptr<DeviceAdapter> adapter,
               bool (*shutdown_requested)());
}

int main(int argc, char **argv) {
    std::signal(SIGINT, on_signal);
    std::signal(SIGTERM, on_signal);
#if defined(_WIN32)
    SetConsoleCtrlHandler(on_console_event, TRUE);
#endif
#if !defined(_WIN32)
    std::signal(SIGPIPE, SIG_IGN);
#endif
    std::uint16_t port = 43120;
    bool simulate = false;
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if (argument == "--port" && index + 1 < argc) {
            const std::string text = argv[++index];
            unsigned value = 0;
            const auto parsed = std::from_chars(text.data(), text.data() + text.size(), value);
            if (parsed.ec != std::errc{} || parsed.ptr != text.data() + text.size() ||
                value > 65535U) {
                std::cerr << "Invalid port\n";
                return 2;
            }
            port = static_cast<std::uint16_t>(value);
        } else if (argument == "--simulate") {
            simulate = true;
            continue;
        } else if (argument == "--version") {
            std::cout << "OrbitHub " << ORBIT_HUB_VERSION << " (protocol "
                      << static_cast<unsigned>(orbit3d::wire::kVersionMajor) << "."
                      << static_cast<unsigned>(orbit3d::wire::kVersionMinor) << ")\n";
            return 0;
        } else if (argument == "--help") {
            std::cout << "Usage: orbithub [--port PORT] [--simulate] [--version]\n";
            return 0;
        } else {
            std::cerr << "Unknown argument: " << argument << '\n';
            return 2;
        }
    }

    std::unique_ptr<orbit3d::hub::DeviceAdapter> adapter;
    if (simulate) {
        adapter = std::make_unique<orbit3d::hub::SimulatorAdapter>();
    }

    return orbit3d::hub::run_server(port, std::move(adapter), shutdown_requested);
}
