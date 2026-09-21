#define ORBIT3D_SDK_BUILD
#include "orbit3d/orbit3d.h"
#include "orbit3d/wire.hpp"
#include "protocol_io.hpp"
#include "socket.hpp"

#include <algorithm>
#include <atomic>
#include <cstring>
#include <deque>
#include <memory>
#include <string>
#include <vector>

struct orbit3d_client {
    orbit3d::net::Socket socket{orbit3d::net::kInvalidSocket};
    std::atomic<std::uint32_t> next_request_id{1};
    std::deque<orbit3d_event> pending_events;
    orbit3d::io::MessageReader reader;
};

namespace {

using orbit3d::wire::Decoder;
using orbit3d::wire::Encoder;
using orbit3d::wire::Message;
using orbit3d::wire::MessageType;

void copy_text(char *output, std::size_t capacity, const std::string &value) {
    if (capacity == 0) {
        return;
    }
    const auto count = std::min(capacity - 1, value.size());
    std::memcpy(output, value.data(), count);
    output[count] = '\0';
}

bool send_request(orbit3d_client *client, MessageType type,
                  const std::vector<std::uint8_t> &payload, std::uint32_t &request_id) {
    request_id = client->next_request_id.fetch_add(1);
    return orbit3d::io::send_message(client->socket, type, request_id, payload);
}

orbit3d_result decode_event(const Message &message, orbit3d_event &event);

orbit3d_result receive_response(orbit3d_client *client, MessageType expected,
                                std::uint32_t request_id, Message &response) {
    try {
        // Unsolicited input can precede the reply, but must not extend this request.
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
        for (;;) {
            const auto remaining = std::chrono::duration_cast<std::chrono::milliseconds>(
                                       deadline - std::chrono::steady_clock::now())
                                       .count();
            if (remaining <= 0) {
                orbit3d::net::shutdown(client->socket);
                return ORBIT3D_TIMEOUT;
            }
            const auto read = client->reader.read(client->socket, response,
                                                  static_cast<std::uint32_t>(remaining));
            if (read == orbit3d::io::ReadResult::timeout) {
                orbit3d::net::shutdown(client->socket);
                return ORBIT3D_TIMEOUT;
            }
            if (read == orbit3d::io::ReadResult::disconnected)
                return ORBIT3D_DISCONNECTED;
            if (response.header.request_id == 0) {
                orbit3d_event event{};
                const auto event_result = decode_event(response, event);
                if (event_result != ORBIT3D_OK) {
                    return event_result;
                }
                client->pending_events.push_back(event);
                if (client->pending_events.size() > 1024) {
                    orbit3d::net::shutdown(client->socket);
                    return ORBIT3D_PROTOCOL_ERROR;
                }
                continue;
            }
            if (response.header.request_id != request_id) {
                return ORBIT3D_PROTOCOL_ERROR;
            }
            if (response.header.type == MessageType::error) {
                return ORBIT3D_PROTOCOL_ERROR;
            }
            return response.header.type == expected ? ORBIT3D_OK : ORBIT3D_PROTOCOL_ERROR;
        }
    } catch (const std::exception &) {
        return ORBIT3D_PROTOCOL_ERROR;
    }
}

orbit3d_result request(orbit3d_client *client, MessageType request_type,
                       const std::vector<std::uint8_t> &payload, MessageType response_type,
                       Message &response) {
    std::uint32_t request_id = 0;
    if (!send_request(client, request_type, payload, request_id)) {
        return ORBIT3D_DISCONNECTED;
    }
    return receive_response(client, response_type, request_id, response);
}

orbit3d_result decode_event(const Message &message, orbit3d_event &event) {
    try {
        Decoder decoder(message.payload);
        event = {};
        switch (message.header.type) {
        case MessageType::motion_event:
            event.type = ORBIT3D_EVENT_MOTION;
            event.data.motion.device_id = decoder.u32();
            event.data.motion.timestamp_us = decoder.u64();
            event.data.motion.tx = decoder.i32();
            event.data.motion.ty = decoder.i32();
            event.data.motion.tz = decoder.i32();
            event.data.motion.rx = decoder.i32();
            event.data.motion.ry = decoder.i32();
            event.data.motion.rz = decoder.i32();
            break;
        case MessageType::button_event:
            event.type = ORBIT3D_EVENT_BUTTON;
            event.data.button.device_id = decoder.u32();
            event.data.button.timestamp_us = decoder.u64();
            event.data.button.button_id = decoder.u16();
            event.data.button.pressed = decoder.u8();
            (void)decoder.u8();
            break;
        case MessageType::button_state:
            event.type = ORBIT3D_EVENT_BUTTON_STATE;
            event.data.button_state.device_id = decoder.u32();
            event.data.button_state.buttons = decoder.u32();
            break;
        case MessageType::device_event:
            event.type = ORBIT3D_EVENT_DEVICE;
            event.data.device.device_id = decoder.u32();
            event.data.device.connected = decoder.u8();
            break;
        default:
            return ORBIT3D_PROTOCOL_ERROR;
        }
        return decoder.empty() ? ORBIT3D_OK : ORBIT3D_PROTOCOL_ERROR;
    } catch (const std::exception &) {
        return ORBIT3D_PROTOCOL_ERROR;
    }
}

} // namespace

extern "C" {

orbit3d_result orbit3d_connect(const char *host, std::uint16_t port, orbit3d_client **out_client) {
    if (host == nullptr || out_client == nullptr || port == 0) {
        return ORBIT3D_INVALID_ARGUMENT;
    }
    *out_client = nullptr;

    auto client = std::make_unique<orbit3d_client>();
    client->socket = orbit3d::net::connect_loopback(host, port);
    if (client->socket == orbit3d::net::kInvalidSocket) {
        return ORBIT3D_IO_ERROR;
    }

    Message response;
    const auto result = request(client.get(), MessageType::hello_request, {},
                                MessageType::hello_response, response);
    if (result != ORBIT3D_OK) {
        orbit3d::net::close(client->socket);
        return result;
    }

    try {
        Decoder decoder(response.payload);
        if (decoder.text() != "OrbitHub") {
            orbit3d::net::close(client->socket);
            return ORBIT3D_PROTOCOL_ERROR;
        }
        (void)decoder.u32();
        if (!decoder.empty()) {
            orbit3d::net::close(client->socket);
            return ORBIT3D_PROTOCOL_ERROR;
        }
    } catch (const std::exception &) {
        orbit3d::net::close(client->socket);
        return ORBIT3D_PROTOCOL_ERROR;
    }

    *out_client = client.release();
    return ORBIT3D_OK;
}

void orbit3d_disconnect(orbit3d_client *client) {
    if (client == nullptr) {
        return;
    }
    orbit3d::net::close(client->socket);
    delete client;
}

orbit3d_result orbit3d_list_devices(orbit3d_client *client, orbit3d_device_info *devices,
                                    std::size_t capacity, std::size_t *out_count) {
    if (client == nullptr || out_count == nullptr || (capacity > 0 && devices == nullptr)) {
        return ORBIT3D_INVALID_ARGUMENT;
    }

    Message response;
    const auto result =
        request(client, MessageType::list_devices_request, {}, MessageType::device_list, response);
    if (result != ORBIT3D_OK) {
        return result;
    }

    try {
        Decoder decoder(response.payload);
        const auto count = static_cast<std::size_t>(decoder.u16());
        *out_count = count;
        for (std::size_t index = 0; index < count; ++index) {
            orbit3d_device_info value{};
            value.device_id = decoder.u32();
            value.capabilities = decoder.u32();
            value.connected = decoder.u8();
            value.button_count = decoder.u8();
            (void)decoder.u16();
            copy_text(value.vendor, sizeof(value.vendor), decoder.text());
            copy_text(value.product, sizeof(value.product), decoder.text());
            copy_text(value.serial, sizeof(value.serial), decoder.text());
            if (index < capacity) {
                devices[index] = value;
            }
        }
        if (!decoder.empty()) {
            return ORBIT3D_PROTOCOL_ERROR;
        }
        return count <= capacity ? ORBIT3D_OK : ORBIT3D_BUFFER_TOO_SMALL;
    } catch (const std::exception &) {
        return ORBIT3D_PROTOCOL_ERROR;
    }
}

orbit3d_result orbit3d_subscribe(orbit3d_client *client, std::uint32_t subscriptions) {
    if (client == nullptr) {
        return ORBIT3D_INVALID_ARGUMENT;
    }
    Encoder encoder;
    encoder.u32(subscriptions);
    Message response;
    const auto result = request(client, MessageType::subscribe_request, encoder.take(),
                                MessageType::subscribe_response, response);
    if (result != ORBIT3D_OK) {
        return result;
    }
    try {
        Decoder decoder(response.payload);
        const auto accepted = decoder.u32();
        return accepted == subscriptions && decoder.empty() ? ORBIT3D_OK : ORBIT3D_PROTOCOL_ERROR;
    } catch (const std::exception &) {
        return ORBIT3D_PROTOCOL_ERROR;
    }
}

orbit3d_result orbit3d_poll(orbit3d_client *client, orbit3d_event *event,
                            std::uint32_t timeout_ms) {
    if (client == nullptr || event == nullptr) {
        return ORBIT3D_INVALID_ARGUMENT;
    }
    *event = {};
    if (!client->pending_events.empty()) {
        *event = client->pending_events.front();
        client->pending_events.pop_front();
        return ORBIT3D_OK;
    }
    try {
        Message message;
        const auto read = client->reader.read(client->socket, message, timeout_ms);
        if (read == orbit3d::io::ReadResult::timeout)
            return ORBIT3D_TIMEOUT;
        if (read == orbit3d::io::ReadResult::disconnected) {
            return ORBIT3D_DISCONNECTED;
        }
        return decode_event(message, *event);
    } catch (const std::exception &) {
        return ORBIT3D_PROTOCOL_ERROR;
    }
}

const char *orbit3d_result_string(orbit3d_result result) {
    switch (result) {
    case ORBIT3D_OK:
        return "ok";
    case ORBIT3D_TIMEOUT:
        return "timeout";
    case ORBIT3D_DISCONNECTED:
        return "disconnected";
    case ORBIT3D_INVALID_ARGUMENT:
        return "invalid argument";
    case ORBIT3D_PROTOCOL_ERROR:
        return "protocol error";
    case ORBIT3D_IO_ERROR:
        return "I/O error";
    case ORBIT3D_BUFFER_TOO_SMALL:
        return "buffer too small";
    }
    return "unknown error";
}

} // extern "C"
