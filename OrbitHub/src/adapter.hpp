#pragma once

#include "orbit3d/wire.hpp"

#include <cstdint>
#include <string>

namespace orbit3d::hub {

struct DeviceDescriptor {
    std::uint32_t id{};
    std::uint32_t capabilities{};
    std::uint8_t button_count{};
    std::string vendor;
    std::string product;
    std::string serial;
};

struct MotionSample {
    std::uint32_t device_id{};
    std::uint64_t timestamp_us{};
    std::int32_t tx{};
    std::int32_t ty{};
    std::int32_t tz{};
    std::int32_t rx{};
    std::int32_t ry{};
    std::int32_t rz{};
};

struct ButtonSample {
    std::uint32_t device_id{};
    std::uint64_t timestamp_us{};
    std::uint16_t button_id{};
    bool pressed{};
};

class AdapterSink {
  public:
    virtual ~AdapterSink() = default;
    virtual void device_connected(const DeviceDescriptor &device) = 0;
    virtual void motion(const MotionSample &sample) = 0;
    virtual void button(const ButtonSample &sample) = 0;
    virtual void device_disconnected(std::uint32_t device_id) = 0;
};

class DeviceAdapter {
  public:
    virtual ~DeviceAdapter() = default;
    virtual bool start(AdapterSink &sink) = 0;
    virtual void stop() = 0;
};

std::uint64_t monotonic_timestamp_us();

} // namespace orbit3d::hub
