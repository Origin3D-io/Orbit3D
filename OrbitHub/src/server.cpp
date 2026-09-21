#include "adapter.hpp"
#include "orbit3d/wire.hpp"
#include "protocol_io.hpp"
#include "socket.hpp"

#include <algorithm>
#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <deque>
#include <iostream>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace orbit3d::hub {

namespace {

struct Client {
    explicit Client(net::Socket socket_value) : socket(socket_value) {}
    ~Client() {
        net::close(socket);
    }

    net::Socket socket{net::kInvalidSocket};
    std::atomic<std::uint32_t> subscriptions{0};
    std::atomic<bool> connected{true};
    std::mutex send_mutex;
    std::condition_variable wake;
    std::deque<wire::Message> outbound;
    std::set<std::uint32_t> provider_devices;
    bool greeted{false};

    void stop() {
        connected = false;
        net::shutdown(socket);
        wake.notify_all();
    }

    void write_loop() {
        while (connected) {
            wire::Message message;
            {
                std::unique_lock<std::mutex> lock(send_mutex);
                wake.wait(lock, [&] { return !connected || !outbound.empty(); });
                if (!connected)
                    break;
                message = std::move(outbound.front());
                outbound.pop_front();
            }
            if (!io::send_message(socket, message.header.type, message.header.request_id,
                                  message.payload))
                stop();
        }
    }
};

bool valid_text(const std::string &text) {
    if (text.size() > 95)
        return false;
    for (std::size_t i = 0; i < text.size();) {
        auto lead = static_cast<unsigned char>(text[i++]);
        if (lead < 0x20 || lead == 0x7f)
            return false;
        if (lead < 0x80)
            continue;
        unsigned count = 0;
        std::uint32_t value = 0, minimum = 0;
        if (lead >= 0xc2 && lead <= 0xdf) {
            count = 1;
            value = lead & 0x1f;
            minimum = 0x80;
        } else if (lead >= 0xe0 && lead <= 0xef) {
            count = 2;
            value = lead & 0x0f;
            minimum = 0x800;
        } else if (lead >= 0xf0 && lead <= 0xf4) {
            count = 3;
            value = lead & 7;
            minimum = 0x10000;
        } else
            return false;
        if (i + count > text.size())
            return false;
        while (count--) {
            auto next = static_cast<unsigned char>(text[i++]);
            if ((next & 0xc0) != 0x80)
                return false;
            value = (value << 6) | (next & 0x3f);
        }
        if (value < minimum || value > 0x10ffff || (value >= 0xd800 && value <= 0xdfff))
            return false;
    }
    return true;
}

std::vector<std::uint8_t>
encode_device_list(const std::map<std::uint32_t, DeviceDescriptor> &devices) {
    wire::Encoder encoder;
    encoder.u16(static_cast<std::uint16_t>(devices.size()));
    for (const auto &entry : devices) {
        const auto &device = entry.second;
        encoder.u32(device.id);
        encoder.u32(device.capabilities);
        encoder.u8(1);
        encoder.u8(device.button_count);
        encoder.u16(0);
        encoder.text(device.vendor);
        encoder.text(device.product);
        encoder.text(device.serial);
    }
    return encoder.take();
}

std::vector<std::uint8_t> encode_motion(const MotionSample &sample) {
    wire::Encoder encoder;
    encoder.u32(sample.device_id);
    encoder.u64(sample.timestamp_us);
    encoder.i32(sample.tx);
    encoder.i32(sample.ty);
    encoder.i32(sample.tz);
    encoder.i32(sample.rx);
    encoder.i32(sample.ry);
    encoder.i32(sample.rz);
    return encoder.take();
}

std::vector<std::uint8_t> encode_button(const ButtonSample &sample) {
    wire::Encoder encoder;
    encoder.u32(sample.device_id);
    encoder.u64(sample.timestamp_us);
    encoder.u16(sample.button_id);
    encoder.u8(sample.pressed ? 1 : 0);
    encoder.u8(0);
    return encoder.take();
}

std::vector<std::uint8_t> encode_device_event(std::uint32_t device_id, bool connected) {
    wire::Encoder encoder;
    encoder.u32(device_id);
    encoder.u8(connected ? 1 : 0);
    return encoder.take();
}

class Server final : public AdapterSink {
  public:
    Server(std::uint16_t port, std::unique_ptr<DeviceAdapter> adapter)
        : requested_port_(port), adapter_(std::move(adapter)) {}

    int run(bool (*shutdown_requested)()) {
        listener_ = net::listen_loopback(requested_port_, actual_port_);
        if (listener_ == net::kInvalidSocket) {
            std::cerr << "OrbitHub could not bind to 127.0.0.1\n";
            return 1;
        }
        if (adapter_ != nullptr && !start_adapter()) {
            std::cerr << "OrbitHub could not start the selected device adapter\n";
            net::close(listener_);
            return 1;
        }

        std::cout << "ORBIT_HUB_READY " << actual_port_ << std::endl;
        while (!stopping_) {
            if (shutdown_requested())
                break;
            if (!net::wait_readable(listener_, 250))
                continue;
            sockaddr_in peer{};
#if defined(_WIN32)
            int peer_length = sizeof(peer);
#else
            socklen_t peer_length = sizeof(peer);
#endif
            const auto socket =
                ::accept(listener_, reinterpret_cast<sockaddr *>(&peer), &peer_length);
            if (socket == net::kInvalidSocket) {
                if (!stopping_) {
                    std::cerr << "OrbitHub accept failed\n";
                }
                break;
            }

            net::configure(socket);
            const auto client = std::make_shared<Client>(socket);
            {
                std::lock_guard<std::mutex> lock(clients_mutex_);
                if (clients_.size() >= 64)
                    continue;
                clients_.push_back(client);
            }
            // run() waits for clients_ to empty before Server or its locks are destroyed.
            std::thread([this, client] { run_client(client); }).detach();
        }

        stopping_ = true;
        stop_adapter();
        net::close(listener_);
        std::unique_lock<std::mutex> lock(clients_mutex_);
        for (const auto &client : clients_)
            client->stop();
        clients_done_.wait(lock, [&] { return clients_.empty(); });
        return 0;
    }

    void device_connected(const DeviceDescriptor &device) override {
        std::lock_guard<std::recursive_mutex> event_lock(events_mutex_);
        {
            std::lock_guard<std::mutex> lock(devices_mutex_);
            devices_[device.id] = device;
        }
        broadcast(wire::MessageType::device_event, wire::subscribe_devices,
                  encode_device_event(device.id, true));
    }

    void motion(const MotionSample &sample) override {
        std::lock_guard<std::recursive_mutex> event_lock(events_mutex_);
        broadcast(wire::MessageType::motion_event, wire::subscribe_motion, encode_motion(sample));
    }

    void button(const ButtonSample &sample) override {
        std::lock_guard<std::recursive_mutex> event_lock(events_mutex_);
        {
            std::lock_guard<std::mutex> lock(devices_mutex_);
            auto &state = provider_button_states_[sample.device_id];
            const auto bit = 1U << (sample.button_id - 1);
            state = sample.pressed ? state | bit : state & ~bit;
        }
        broadcast(wire::MessageType::button_event, wire::subscribe_buttons, encode_button(sample));
    }

    void device_disconnected(std::uint32_t device_id) override {
        std::lock_guard<std::recursive_mutex> event_lock(events_mutex_);
        std::vector<ButtonSample> releases;
        {
            std::lock_guard<std::mutex> lock(devices_mutex_);
            const auto state = provider_button_states_.find(device_id);
            if (state != provider_button_states_.end()) {
                const auto now = monotonic_timestamp_us();
                for (std::uint16_t index = 0; index < 32; ++index) {
                    const auto bit = 1U << index;
                    if ((state->second & bit) != 0U) {
                        releases.push_back(
                            {device_id, now, static_cast<std::uint16_t>(index + 1), false});
                    }
                }
                provider_button_states_.erase(state);
            }
            devices_.erase(device_id);
        }
        for (const auto &release : releases) {
            broadcast(wire::MessageType::button_event, wire::subscribe_buttons,
                      encode_button(release));
        }
        broadcast(wire::MessageType::device_event, wire::subscribe_devices,
                  encode_device_event(device_id, false));
    }

  private:
    void run_client(const std::shared_ptr<Client> &client) {
        std::thread writer([client] { client->write_loop(); });
        try {
            wire::Message message;
            io::MessageReader reader;
            auto last_message = std::chrono::steady_clock::now();
            const auto hello_deadline = last_message + std::chrono::seconds(2);
            auto partial_since = last_message;
            bool had_partial = false;
            while (!stopping_ && client->connected) {
                if (!client->greeted && std::chrono::steady_clock::now() >= hello_deadline)
                    break;
                const auto result = reader.read(client->socket, message, 250);
                if (result == io::ReadResult::disconnected)
                    break;
                if (result == io::ReadResult::timeout) {
                    const auto now = std::chrono::steady_clock::now();
                    const auto idle = now - last_message;
                    if (reader.partial() && !had_partial) {
                        partial_since = now;
                        had_partial = true;
                    }
                    if (had_partial && now - partial_since > std::chrono::seconds(2))
                        break;
                    if (!client->greeted && now >= hello_deadline)
                        break;
                    if (!client->provider_devices.empty() && idle > std::chrono::seconds(3))
                        break;
                    continue;
                }
                last_message = std::chrono::steady_clock::now();
                had_partial = false;
                try {
                    std::lock_guard<std::recursive_mutex> event_lock(events_mutex_);
                    handle_message(client, message);
                } catch (const std::exception &) {
                    if (message.header.request_id != 0) {
                        send_error(client, message.header.request_id, "Invalid request payload");
                    } else {
                        client->connected = false;
                    }
                }
            }
        } catch (const std::exception &) {
        }
        client->stop();
        writer.join();
        {
            std::lock_guard<std::recursive_mutex> event_lock(events_mutex_);
            disconnect_provider_devices(*client);
        }
        std::lock_guard<std::mutex> lock(clients_mutex_);
        clients_.erase(std::remove(clients_.begin(), clients_.end(), client), clients_.end());
        clients_done_.notify_all();
    }

    void handle_message(const std::shared_ptr<Client> &client, const wire::Message &message) {
        if (!client->greeted && message.header.type != wire::MessageType::hello_request)
            throw std::runtime_error("Hello required");
        const bool one_way = message.header.type == wire::MessageType::provider_motion ||
                             message.header.type == wire::MessageType::provider_button;
        if (!one_way && message.header.request_id == 0)
            throw std::runtime_error("Request ID required");
        if ((message.header.type == wire::MessageType::hello_request ||
             message.header.type == wire::MessageType::list_devices_request ||
             message.header.type == wire::MessageType::ping) &&
            !message.payload.empty())
            throw std::runtime_error("Empty payload required");
        switch (message.header.type) {
        case wire::MessageType::hello_request: {
            client->greeted = true;
            wire::Encoder payload;
            payload.text("OrbitHub");
            payload.u32(wire::server_capability_consumer | wire::server_capability_provider);
            send(client, wire::MessageType::hello_response, message.header.request_id,
                 payload.take());
            break;
        }
        case wire::MessageType::list_devices_request: {
            std::map<std::uint32_t, DeviceDescriptor> devices;
            {
                std::lock_guard<std::mutex> lock(devices_mutex_);
                devices = devices_;
            }
            send(client, wire::MessageType::device_list, message.header.request_id,
                 encode_device_list(devices));
            break;
        }
        case wire::MessageType::subscribe_request: {
            wire::Decoder decoder(message.payload);
            const auto requested = decoder.u32();
            if (!decoder.empty())
                throw std::runtime_error("Invalid subscription");
            const auto allowed = requested & (wire::subscribe_motion | wire::subscribe_buttons |
                                              wire::subscribe_devices);
            wire::Encoder payload;
            payload.u32(allowed);
            send(client, wire::MessageType::subscribe_response, message.header.request_id,
                 payload.take());
            client->subscriptions = allowed;
            if ((allowed & wire::subscribe_buttons) != 0) {
                std::lock_guard<std::mutex> lock(devices_mutex_);
                for (const auto &entry : devices_) {
                    wire::Encoder state;
                    state.u32(entry.first);
                    state.u32(provider_button_states_[entry.first]);
                    send(client, wire::MessageType::button_state, 0, state.take());
                }
            }
            break;
        }
        case wire::MessageType::ping:
            send(client, wire::MessageType::pong, message.header.request_id, {});
            break;
        case wire::MessageType::provider_register_request:
            register_provider_device(client, message);
            break;
        case wire::MessageType::provider_unregister_request:
            unregister_provider_device(client, message);
            break;
        case wire::MessageType::provider_motion:
            receive_provider_motion(client, message);
            break;
        case wire::MessageType::provider_button:
            receive_provider_button(client, message);
            break;
        default:
            send_error(client, message.header.request_id, "Unsupported request type");
            break;
        }
    }

    void send(const std::shared_ptr<Client> &client, wire::MessageType type,
              std::uint32_t request_id, const std::vector<std::uint8_t> &payload) {
        std::lock_guard<std::mutex> lock(client->send_mutex);
        if (!client->connected)
            return;
        if (type == wire::MessageType::motion_event) {
            // Replace obsolete velocity samples, but never cross a button/device/response
            // boundary: doing so would change the ordering observed by the consumer.
            for (auto it = client->outbound.rbegin(); it != client->outbound.rend(); ++it) {
                if (it->header.type != type)
                    break;
                if (std::equal(payload.begin(), payload.begin() + 4, it->payload.begin())) {
                    it->payload = payload;
                    return;
                }
            }
        }
        if (client->outbound.size() >= 256) {
            client->stop();
            return;
        }
        client->outbound.push_back(
            {{type, static_cast<std::uint32_t>(payload.size()), request_id}, payload});
        client->wake.notify_one();
    }

    void send_error(const std::shared_ptr<Client> &client, std::uint32_t request_id,
                    const std::string &message) {
        wire::Encoder payload;
        payload.text(message);
        send(client, wire::MessageType::error, request_id, payload.take());
    }

    void broadcast(wire::MessageType type, std::uint32_t subscription,
                   const std::vector<std::uint8_t> &payload) {
        std::vector<std::shared_ptr<Client>> clients;
        {
            std::lock_guard<std::mutex> lock(clients_mutex_);
            clients = clients_;
        }
        for (const auto &client : clients) {
            if ((client->subscriptions.load() & subscription) != 0U) {
                send(client, type, 0, payload);
            }
        }
    }

    void register_provider_device(const std::shared_ptr<Client> &client,
                                  const wire::Message &message) {
        if (message.header.request_id == 0) {
            throw std::runtime_error("Provider registration requires a response");
        }
        wire::Decoder decoder(message.payload);
        const auto capabilities = decoder.u32();
        const auto button_count = decoder.u8();
        const auto reserved_1 = decoder.u8();
        const auto reserved_2 = decoder.u8();
        const auto reserved_3 = decoder.u8();
        const auto vendor = decoder.text();
        const auto product = decoder.text();
        const auto serial = decoder.text();
        const auto allowed = wire::capability_motion_6dof | wire::capability_buttons;
        if (!decoder.empty() || vendor.empty() || product.empty() || !valid_text(vendor) ||
            !valid_text(product) || !valid_text(serial) || reserved_1 != 0 || reserved_2 != 0 ||
            reserved_3 != 0 || (capabilities & wire::capability_motion_6dof) == 0U ||
            (capabilities & ~allowed) != 0U || button_count > 32 ||
            (((capabilities & wire::capability_buttons) != 0U) != (button_count > 0))) {
            send_error(client, message.header.request_id, "Invalid provider device description");
            return;
        }

        DeviceDescriptor device;
        {
            std::lock_guard<std::mutex> lock(devices_mutex_);
            if (devices_.size() >= 32) {
                send_error(client, message.header.request_id, "Device limit reached");
                return;
            }
            while (devices_.count(next_provider_device_id_) != 0U) {
                ++next_provider_device_id_;
            }
            device = {
                next_provider_device_id_++, capabilities, button_count, vendor, product, serial,
            };
            devices_[device.id] = device;
            provider_button_states_[device.id] = 0;
        }
        client->provider_devices.insert(device.id);
        broadcast(wire::MessageType::device_event, wire::subscribe_devices,
                  encode_device_event(device.id, true));
        wire::Encoder response;
        response.u32(device.id);
        send(client, wire::MessageType::provider_register_response, message.header.request_id,
             response.take());
    }

    void unregister_provider_device(const std::shared_ptr<Client> &client,
                                    const wire::Message &message) {
        if (message.header.request_id == 0) {
            throw std::runtime_error("Provider unregister requires a response");
        }
        wire::Decoder decoder(message.payload);
        const auto device_id = decoder.u32();
        if (!decoder.empty() || client->provider_devices.erase(device_id) == 0U) {
            send_error(client, message.header.request_id, "Provider does not own this device");
            return;
        }
        device_disconnected(device_id);
        send(client, wire::MessageType::provider_unregister_response, message.header.request_id,
             {});
    }

    void receive_provider_motion(const std::shared_ptr<Client> &client,
                                 const wire::Message &message) {
        if (message.header.request_id != 0) {
            throw std::runtime_error("Provider motion must be one-way");
        }
        wire::Decoder decoder(message.payload);
        MotionSample sample;
        sample.device_id = decoder.u32();
        sample.timestamp_us = decoder.u64();
        sample.tx = decoder.i32();
        sample.ty = decoder.i32();
        sample.tz = decoder.i32();
        sample.rx = decoder.i32();
        sample.ry = decoder.i32();
        sample.rz = decoder.i32();
        const auto valid_axis = [](std::int32_t value) {
            return value >= -1000000 && value <= 1000000;
        };
        if (!decoder.empty() || client->provider_devices.count(sample.device_id) == 0U ||
            !valid_axis(sample.tx) || !valid_axis(sample.ty) || !valid_axis(sample.tz) ||
            !valid_axis(sample.rx) || !valid_axis(sample.ry) || !valid_axis(sample.rz)) {
            throw std::runtime_error("Invalid provider motion");
        }
        sample.timestamp_us = monotonic_timestamp_us();
        motion(sample);
    }

    void receive_provider_button(const std::shared_ptr<Client> &client,
                                 const wire::Message &message) {
        if (message.header.request_id != 0) {
            throw std::runtime_error("Provider button must be one-way");
        }
        wire::Decoder decoder(message.payload);
        ButtonSample sample;
        sample.device_id = decoder.u32();
        sample.timestamp_us = decoder.u64();
        sample.button_id = decoder.u16();
        const auto pressed = decoder.u8();
        const auto reserved = decoder.u8();
        sample.pressed = pressed != 0;
        std::uint8_t button_count = 0;
        bool changed = false;
        {
            std::lock_guard<std::mutex> lock(devices_mutex_);
            const auto found = devices_.find(sample.device_id);
            if (found != devices_.end()) {
                button_count = found->second.button_count;
            }
            if (!decoder.empty() || pressed > 1 || reserved != 0 ||
                client->provider_devices.count(sample.device_id) == 0U || sample.button_id == 0 ||
                sample.button_id > button_count) {
                throw std::runtime_error("Invalid provider button");
            }
            const auto bit = 1U << (sample.button_id - 1U);
            auto &state = provider_button_states_[sample.device_id];
            changed = ((state & bit) != 0U) != sample.pressed;
            state = sample.pressed ? state | bit : state & ~bit;
        }
        if (changed) {
            sample.timestamp_us = monotonic_timestamp_us();
            button(sample);
        }
    }

    void disconnect_provider_devices(Client &client) {
        const auto devices = client.provider_devices;
        client.provider_devices.clear();
        for (const auto device_id : devices) {
            device_disconnected(device_id);
        }
    }

    bool start_adapter() {
        std::lock_guard<std::mutex> lock(adapter_mutex_);
        if (adapter_ == nullptr) {
            return false;
        }
        if (adapter_running_) {
            return true;
        }
        adapter_running_ = adapter_->start(*this);
        return adapter_running_;
    }

    void stop_adapter() {
        std::lock_guard<std::mutex> lock(adapter_mutex_);
        if (adapter_ != nullptr && adapter_running_) {
            adapter_->stop();
            adapter_running_ = false;
        }
    }

    std::uint16_t requested_port_{};
    // Event handlers may call motion(), button(), or device_disconnected() while
    // already holding this lock. Recursion keeps each request and its events atomic.
    // Acquire events before devices/clients, and send_mutex last. Never acquire
    // events from a writer or while holding devices/clients. adapter_mutex_ is
    // lifecycle-only; callbacks must not acquire it (stop() may join their thread).
    std::recursive_mutex events_mutex_;
    std::uint16_t actual_port_{};
    net::Socket listener_{net::kInvalidSocket};
    std::atomic<bool> stopping_{false};
    std::unique_ptr<DeviceAdapter> adapter_;
    std::mutex adapter_mutex_;
    bool adapter_running_{};
    std::mutex devices_mutex_;
    std::map<std::uint32_t, DeviceDescriptor> devices_;
    std::map<std::uint32_t, std::uint32_t> provider_button_states_;
    // Keep provider allocations above the built-in adapter range (simulator: 1).
    // These are session-local handles, not stable hardware identities.
    std::uint32_t next_provider_device_id_{0x00010000U};
    std::mutex clients_mutex_;
    std::condition_variable clients_done_;
    std::vector<std::shared_ptr<Client>> clients_;
};

} // namespace

int run_server(std::uint16_t port, std::unique_ptr<DeviceAdapter> adapter,
               bool (*shutdown_requested)()) {
    Server server(port, std::move(adapter));
    return server.run(shutdown_requested);
}

} // namespace orbit3d::hub
