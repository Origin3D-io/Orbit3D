#pragma once

#include "orbit3d/wire.hpp"
#include "socket.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <mutex>

namespace orbit3d::io {

enum class ReadResult { message, timeout, disconnected };

class MessageReader {
  public:
    ReadResult read(net::Socket socket, wire::Message &message, std::uint32_t timeout_ms) {
        const auto deadline =
            std::chrono::steady_clock::now() + std::chrono::milliseconds(timeout_ms);
        bool received = false;
        for (;;) {
            std::size_t required = wire::kHeaderSize;
            if (buffer_.size() >= wire::kHeaderSize) {
                std::array<std::uint8_t, wire::kHeaderSize> header{};
                std::copy_n(buffer_.begin(), header.size(), header.begin());
                message.header = wire::decode_header(header);
                required += message.header.payload_size;
                if (buffer_.size() == required) {
                    message.payload.assign(buffer_.begin() + wire::kHeaderSize, buffer_.end());
                    buffer_.clear();
                    return ReadResult::message;
                }
            }
            const auto now = std::chrono::steady_clock::now();
            // A zero-timeout poll still gets one nonblocking read. After progress,
            // stop at the deadline rather than chasing a continuously arriving packet.
            if (received && now >= deadline)
                return ReadResult::timeout;
            const auto remaining =
                now < deadline
                    ? std::chrono::duration_cast<std::chrono::milliseconds>(deadline - now).count()
                    : 0;
            if (!net::wait_readable(socket, static_cast<std::uint32_t>(remaining))) {
                return ReadResult::timeout;
            }
            std::array<std::uint8_t, 4096> chunk{};
            const auto count =
                ::recv(socket, reinterpret_cast<char *>(chunk.data()),
                       static_cast<int>(std::min(chunk.size(), required - buffer_.size())), 0);
            if (count <= 0)
                return ReadResult::disconnected;
            buffer_.insert(buffer_.end(), chunk.begin(), chunk.begin() + count);
            received = true;
        }
    }
    bool partial() const noexcept {
        return !buffer_.empty();
    }

  private:
    std::vector<std::uint8_t> buffer_;
};

inline bool send_message(net::Socket socket, wire::MessageType type, std::uint32_t request_id,
                         const std::vector<std::uint8_t> &payload,
                         std::mutex *send_mutex = nullptr) {
    const auto send = [&] {
        const auto header =
            wire::encode_header({type, static_cast<std::uint32_t>(payload.size()), request_id});
        return net::send_all(socket, header.data(), header.size()) &&
               (payload.empty() || net::send_all(socket, payload.data(), payload.size()));
    };

    if (send_mutex != nullptr) {
        std::lock_guard<std::mutex> lock(*send_mutex);
        return send();
    }
    return send();
}

inline bool receive_message(net::Socket socket, wire::Message &message) {
    std::array<std::uint8_t, wire::kHeaderSize> header_bytes{};
    if (!net::receive_all(socket, header_bytes.data(), header_bytes.size())) {
        return false;
    }
    message.header = wire::decode_header(header_bytes);
    message.payload.resize(message.header.payload_size);
    return message.payload.empty() ||
           net::receive_all(socket, message.payload.data(), message.payload.size());
}

} // namespace orbit3d::io
