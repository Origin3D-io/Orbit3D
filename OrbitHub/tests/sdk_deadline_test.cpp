#include "orbit3d/orbit3d.h"
#include "orbit3d/wire.hpp"
#include "protocol_io.hpp"
#include "socket.hpp"
#include <chrono>
#include <iostream>
#include <thread>
#if !defined(_WIN32)
#include <fcntl.h>
#endif

int main() {
    using namespace orbit3d;
#if !defined(_WIN32)
    int pair[2];
    if (::socketpair(AF_UNIX, SOCK_STREAM, 0, pair) != 0)
        return 1;
    const int high = ::fcntl(pair[0], F_DUPFD, FD_SETSIZE);
    if (high >= 0) {
        const std::uint8_t byte = 1;
        net::send_all(pair[1], &byte, 1);
        const bool readable = net::wait_readable(high, 100);
        net::close(high);
        if (!readable)
            return 1;
    } else {
        std::cout << "High-descriptor test skipped: process descriptor limit\n";
    }
    net::close(pair[0]);
    net::close(pair[1]);
#endif
    std::uint16_t port = 0;
    const auto listener = net::listen_loopback(0, port);
    if (listener == net::kInvalidSocket)
        return 1;
    std::thread peer([&] {
        const auto socket = ::accept(listener, nullptr, nullptr);
        wire::Message request;
        io::receive_message(socket, request);
        wire::Encoder hello;
        hello.text("OrbitHub");
        hello.u32(3);
        io::send_message(socket, wire::MessageType::hello_response, request.header.request_id,
                         hello.take());
        wire::Encoder motion;
        motion.u32(1);
        motion.u64(1);
        for (int axis = 0; axis < 6; ++axis)
            motion.i32(123);
        const auto payload = motion.take();
        const auto header = wire::encode_header({wire::MessageType::motion_event, 36, 0});
        net::send_all(socket, header.data(), 8);
        std::this_thread::sleep_for(std::chrono::milliseconds(150));
        net::send_all(socket, header.data() + 8, header.size() - 8);
        net::send_all(socket, payload.data(), payload.size());
        net::close(socket);
    });
    orbit3d_client *client = nullptr;
    auto result = orbit3d_connect("127.0.0.1", port, &client);
    bool passed = result == ORBIT3D_OK;
    if (passed) {
        orbit3d_event event{};
        const auto start = std::chrono::steady_clock::now();
        passed = orbit3d_poll(client, &event, 20) == ORBIT3D_TIMEOUT;
        passed =
            passed && std::chrono::steady_clock::now() - start < std::chrono::milliseconds(100);
        result = orbit3d_poll(client, &event, 1000);
        passed = passed && result == ORBIT3D_OK && event.type == ORBIT3D_EVENT_MOTION &&
                 event.data.motion.tx == 123;
    }
    orbit3d_disconnect(client);
    peer.join();
    net::close(listener);
    if (!passed)
        std::cerr << "SDK packet deadline regression\n";
    return passed ? 0 : 1;
}
