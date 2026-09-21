#include "orbit3d/wire.hpp"

#include <algorithm>
#include <limits>

namespace orbit3d::wire {

namespace {

void append_be(std::vector<std::uint8_t> &output, std::uint64_t value, std::size_t count) {
    for (std::size_t index = 0; index < count; ++index) {
        const auto shift = static_cast<unsigned>((count - index - 1) * 8);
        output.push_back(static_cast<std::uint8_t>((value >> shift) & 0xFFU));
    }
}

std::uint64_t read_be(const std::vector<std::uint8_t> &input, std::size_t offset,
                      std::size_t count) {
    std::uint64_t value = 0;
    for (std::size_t index = 0; index < count; ++index) {
        value = (value << 8U) | input[offset + index];
    }
    return value;
}

} // namespace

void Encoder::u8(std::uint8_t value) {
    bytes_.push_back(value);
}

void Encoder::u16(std::uint16_t value) {
    append_be(bytes_, value, 2);
}

void Encoder::u32(std::uint32_t value) {
    append_be(bytes_, value, 4);
}

void Encoder::u64(std::uint64_t value) {
    append_be(bytes_, value, 8);
}

void Encoder::i32(std::int32_t value) {
    u32(static_cast<std::uint32_t>(value));
}

void Encoder::text(std::string_view value) {
    if (value.size() > std::numeric_limits<std::uint16_t>::max()) {
        throw std::length_error("Orbit3D text field is too long");
    }
    u16(static_cast<std::uint16_t>(value.size()));
    bytes_.insert(bytes_.end(), value.begin(), value.end());
}

const std::vector<std::uint8_t> &Encoder::bytes() const noexcept {
    return bytes_;
}

std::vector<std::uint8_t> Encoder::take() {
    return std::move(bytes_);
}

Decoder::Decoder(const std::vector<std::uint8_t> &bytes) : bytes_(bytes) {}

void Decoder::require(std::size_t count) const {
    if (count > bytes_.size() - std::min(offset_, bytes_.size())) {
        throw std::runtime_error("Orbit3D message is truncated");
    }
}

std::uint8_t Decoder::u8() {
    require(1);
    return bytes_[offset_++];
}

std::uint16_t Decoder::u16() {
    require(2);
    const auto value = static_cast<std::uint16_t>(read_be(bytes_, offset_, 2));
    offset_ += 2;
    return value;
}

std::uint32_t Decoder::u32() {
    require(4);
    const auto value = static_cast<std::uint32_t>(read_be(bytes_, offset_, 4));
    offset_ += 4;
    return value;
}

std::uint64_t Decoder::u64() {
    require(8);
    const auto value = read_be(bytes_, offset_, 8);
    offset_ += 8;
    return value;
}

std::int32_t Decoder::i32() {
    return static_cast<std::int32_t>(u32());
}

std::string Decoder::text() {
    const auto length = u16();
    require(length);
    const auto begin = bytes_.begin() + static_cast<std::ptrdiff_t>(offset_);
    offset_ += length;
    return std::string(begin, begin + length);
}

bool Decoder::empty() const noexcept {
    return offset_ == bytes_.size();
}

std::array<std::uint8_t, kHeaderSize> encode_header(const Header &header) {
    if (header.payload_size > kMaxPayloadSize) {
        throw std::length_error("Orbit3D payload exceeds the protocol limit");
    }

    std::array<std::uint8_t, kHeaderSize> bytes{};
    std::copy(kMagic.begin(), kMagic.end(), bytes.begin());
    bytes[4] = kVersionMajor;
    bytes[5] = kVersionMinor;
    bytes[6] = static_cast<std::uint8_t>((static_cast<std::uint16_t>(header.type) >> 8U) & 0xFFU);
    bytes[7] = static_cast<std::uint8_t>(static_cast<std::uint16_t>(header.type) & 0xFFU);
    for (std::size_t index = 0; index < 4; ++index) {
        const auto shift = static_cast<unsigned>((3 - index) * 8);
        bytes[8 + index] = static_cast<std::uint8_t>((header.payload_size >> shift) & 0xFFU);
        bytes[12 + index] = static_cast<std::uint8_t>((header.request_id >> shift) & 0xFFU);
    }
    return bytes;
}

Header decode_header(const std::array<std::uint8_t, kHeaderSize> &bytes) {
    if (!std::equal(kMagic.begin(), kMagic.end(), bytes.begin())) {
        throw std::runtime_error("Invalid Orbit3D message magic");
    }
    if (bytes[4] != kVersionMajor || bytes[5] != kVersionMinor) {
        throw std::runtime_error("Unsupported Orbit3D protocol version");
    }

    Header header;
    header.type = static_cast<MessageType>((static_cast<std::uint16_t>(bytes[6]) << 8U) | bytes[7]);
    for (std::size_t index = 0; index < 4; ++index) {
        header.payload_size = (header.payload_size << 8U) | bytes[8 + index];
        header.request_id = (header.request_id << 8U) | bytes[12 + index];
    }
    if (header.payload_size > kMaxPayloadSize) {
        throw std::runtime_error("Orbit3D payload exceeds the protocol limit");
    }
    return header;
}

} // namespace orbit3d::wire
