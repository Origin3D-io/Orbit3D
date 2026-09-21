#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace orbit3d::wire {

constexpr std::array<std::uint8_t, 4> kMagic{'O', '3', 'D', 'H'};
constexpr std::uint8_t kVersionMajor = 0;
constexpr std::uint8_t kVersionMinor = 2;
constexpr std::size_t kHeaderSize = 16;
constexpr std::uint32_t kMaxPayloadSize = 64 * 1024;

enum class MessageType : std::uint16_t {
    hello_request = 1,
    hello_response = 2,
    list_devices_request = 3,
    device_list = 4,
    subscribe_request = 5,
    subscribe_response = 6,
    motion_event = 7,
    button_event = 8,
    device_event = 9,
    ping = 10,
    pong = 11,
    provider_register_request = 12,
    provider_register_response = 13,
    provider_unregister_request = 14,
    provider_unregister_response = 15,
    provider_motion = 16,
    provider_button = 17,
    button_state = 18,
    error = 255,
};

enum Subscription : std::uint32_t {
    subscribe_motion = 1U << 0,
    subscribe_buttons = 1U << 1,
    subscribe_devices = 1U << 2,
};

enum Capability : std::uint32_t {
    capability_motion_6dof = 1U << 0,
    capability_buttons = 1U << 1,
};

enum ServerCapability : std::uint32_t {
    server_capability_consumer = 1U << 0,
    server_capability_provider = 1U << 1,
};

struct Header {
    MessageType type{};
    std::uint32_t payload_size{};
    std::uint32_t request_id{};
};

struct Message {
    Header header;
    std::vector<std::uint8_t> payload;
};

class Encoder {
  public:
    void u8(std::uint8_t value);
    void u16(std::uint16_t value);
    void u32(std::uint32_t value);
    void u64(std::uint64_t value);
    void i32(std::int32_t value);
    void text(std::string_view value);

    const std::vector<std::uint8_t> &bytes() const noexcept;
    std::vector<std::uint8_t> take();

  private:
    std::vector<std::uint8_t> bytes_;
};

class Decoder {
  public:
    explicit Decoder(const std::vector<std::uint8_t> &bytes);

    std::uint8_t u8();
    std::uint16_t u16();
    std::uint32_t u32();
    std::uint64_t u64();
    std::int32_t i32();
    std::string text();
    bool empty() const noexcept;

  private:
    void require(std::size_t count) const;

    const std::vector<std::uint8_t> &bytes_;
    std::size_t offset_{};
};

std::array<std::uint8_t, kHeaderSize> encode_header(const Header &header);
Header decode_header(const std::array<std::uint8_t, kHeaderSize> &bytes);

} // namespace orbit3d::wire
