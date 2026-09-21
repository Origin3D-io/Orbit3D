#pragma once

#include "orbit3d/orbit3d.h"

#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

namespace orbit3d {

class Error : public std::runtime_error {
  public:
    explicit Error(orbit3d_result result)
        : std::runtime_error(orbit3d_result_string(result)), result_(result) {}

    orbit3d_result result() const noexcept {
        return result_;
    }

  private:
    orbit3d_result result_;
};

class Client {
  public:
    Client(const std::string &host = "127.0.0.1", std::uint16_t port = 43120) {
        const auto result = orbit3d_connect(host.c_str(), port, &client_);
        if (result != ORBIT3D_OK) {
            throw Error(result);
        }
    }

    ~Client() {
        orbit3d_disconnect(client_);
    }

    Client(const Client &) = delete;
    Client &operator=(const Client &) = delete;

    std::vector<orbit3d_device_info> devices() {
        std::vector<orbit3d_device_info> result(ORBIT3D_MAX_DEVICES);
        std::size_t count = 0;
        const auto status = orbit3d_list_devices(client_, result.data(), result.size(), &count);
        if (status != ORBIT3D_OK) {
            throw Error(status);
        }
        result.resize(count);
        return result;
    }

    void subscribe(std::uint32_t subscriptions) {
        const auto result = orbit3d_subscribe(client_, subscriptions);
        if (result != ORBIT3D_OK) {
            throw Error(result);
        }
    }

    orbit3d_result poll(orbit3d_event &event, std::uint32_t timeout_ms) {
        return orbit3d_poll(client_, &event, timeout_ms);
    }

  private:
    orbit3d_client *client_{};
};

} // namespace orbit3d
