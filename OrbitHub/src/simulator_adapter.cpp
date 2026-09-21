#include "simulator_adapter.hpp"

#include <chrono>
#include <cmath>
#include <cstdint>

namespace orbit3d::hub {

namespace {

constexpr std::uint32_t kDeviceId = 1;

DeviceDescriptor descriptor() {
    return {
        kDeviceId,
        wire::capability_motion_6dof | wire::capability_buttons,
        4,
        "Orbit3D",
        "Orbit3D Simulator",
        "SIM-0001",
    };
}

} // namespace

SimulatorAdapter::~SimulatorAdapter() {
    stop();
}

bool SimulatorAdapter::start(AdapterSink &sink) {
    if (running_.exchange(true)) {
        return false;
    }
    sink_ = &sink;
    thread_ = std::thread([this] { run(); });
    return true;
}

void SimulatorAdapter::stop() {
    running_ = false;
    if (thread_.joinable()) {
        thread_.join();
    }
    sink_ = nullptr;
}

void SimulatorAdapter::run() {
    const auto device = descriptor();
    sink_->device_connected(device);

    constexpr double kTau = 6.28318530717958647692;
    std::uint64_t frame = 0;
    bool button_pressed = false;
    while (running_) {
        const auto phase = static_cast<double>(frame % 200U) / 200.0 * kTau;
        const auto value = [](double input) {
            return static_cast<std::int32_t>(std::lround(input * 500000.0));
        };
        const auto now = monotonic_timestamp_us();
        sink_->motion({
            device.id,
            now,
            value(std::sin(phase)),
            value(std::cos(phase)),
            value(std::sin(phase * 0.5)),
            value(std::cos(phase * 0.5)),
            value(std::sin(phase * 0.25)),
            value(std::cos(phase * 0.25)),
        });

        if (frame > 0 && frame % 25U == 0U) {
            button_pressed = !button_pressed;
            sink_->button({device.id, now, 1, button_pressed});
        }

        ++frame;
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }

    if (button_pressed) {
        sink_->button({device.id, monotonic_timestamp_us(), 1, false});
    }
    sink_->device_disconnected(device.id);
}

} // namespace orbit3d::hub
