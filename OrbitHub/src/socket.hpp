#pragma once

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <arpa/inet.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <poll.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <unistd.h>
#endif

namespace orbit3d::net {

#if defined(_WIN32)
using Socket = SOCKET;
constexpr Socket kInvalidSocket = INVALID_SOCKET;
#else
using Socket = int;
constexpr Socket kInvalidSocket = -1;
#endif

inline void initialize() {
#if defined(_WIN32)
    static const bool initialized = [] {
        WSADATA data{};
        if (WSAStartup(MAKEWORD(2, 2), &data) != 0) {
            throw std::runtime_error("WSAStartup failed");
        }
        return true;
    }();
    (void)initialized;
#endif
}

inline void close(Socket socket) {
    if (socket == kInvalidSocket) {
        return;
    }
#if defined(_WIN32)
    closesocket(socket);
#else
    ::close(socket);
#endif
}

inline bool wait_readable(Socket socket, std::uint32_t timeout_ms) {
#if !defined(_WIN32)
    // poll accepts descriptor values above FD_SETSIZE in embedded SDK hosts.
    pollfd descriptor{socket, POLLIN, 0};
    const auto timeout = static_cast<int>(std::min<std::uint32_t>(timeout_ms, 2147483647U));
    return ::poll(&descriptor, 1, timeout) > 0 &&
           (descriptor.revents & (POLLIN | POLLHUP | POLLERR | POLLNVAL)) != 0;
#else
    fd_set read_set;
    FD_ZERO(&read_set);
    FD_SET(socket, &read_set);
    timeval timeout{};
    timeout.tv_sec = static_cast<long>(timeout_ms / 1000U);
    timeout.tv_usec = static_cast<long>((timeout_ms % 1000U) * 1000U);
    const auto result = select(0, &read_set, nullptr, nullptr, &timeout);
    return result > 0 && FD_ISSET(socket, &read_set);
#endif
}

inline void shutdown(Socket socket) {
#if defined(_WIN32)
    ::shutdown(socket, SD_BOTH);
#else
    ::shutdown(socket, SHUT_RDWR);
#endif
}

inline void configure(Socket socket) {
    int no_delay = 1;
    setsockopt(socket, IPPROTO_TCP, TCP_NODELAY, reinterpret_cast<const char *>(&no_delay),
               sizeof(no_delay));
#if defined(_WIN32)
    DWORD timeout = 500;
#else
    timeval timeout{0, 500000};
#endif
    setsockopt(socket, SOL_SOCKET, SO_SNDTIMEO, reinterpret_cast<const char *>(&timeout),
               sizeof(timeout));
#if defined(SO_NOSIGPIPE)
    int enabled = 1;
    setsockopt(socket, SOL_SOCKET, SO_NOSIGPIPE, &enabled, sizeof(enabled));
#endif
}

inline bool send_all(Socket socket, const std::uint8_t *data, std::size_t size) {
    std::size_t sent = 0;
    while (sent < size) {
        const auto count = ::send(socket, reinterpret_cast<const char *>(data + sent),
                                  static_cast<int>(size - sent),
#if defined(MSG_NOSIGNAL)
                                  MSG_NOSIGNAL);
#else
                                  0);
#endif
        if (count <= 0) {
            return false;
        }
        sent += static_cast<std::size_t>(count);
    }
    return true;
}

inline bool receive_all(Socket socket, std::uint8_t *data, std::size_t size) {
    std::size_t received = 0;
    while (received < size) {
        const auto count = ::recv(socket, reinterpret_cast<char *>(data + received),
                                  static_cast<int>(size - received), 0);
        if (count <= 0) {
            return false;
        }
        received += static_cast<std::size_t>(count);
    }
    return true;
}

inline Socket connect_loopback(const std::string &host, std::uint16_t port) {
    initialize();
    const auto socket = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (socket == kInvalidSocket) {
        return kInvalidSocket;
    }

    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_port = htons(port);
    if (inet_pton(AF_INET, host.c_str(), &address.sin_addr) != 1 ||
        ::connect(socket, reinterpret_cast<sockaddr *>(&address), sizeof(address)) != 0) {
        close(socket);
        return kInvalidSocket;
    }
    configure(socket);
    return socket;
}

inline Socket listen_loopback(std::uint16_t requested_port, std::uint16_t &actual_port) {
    initialize();
    const auto socket = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (socket == kInvalidSocket) {
        return kInvalidSocket;
    }

    int reuse = 1;
    setsockopt(socket, SOL_SOCKET, SO_REUSEADDR, reinterpret_cast<const char *>(&reuse),
               sizeof(reuse));

    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_port = htons(requested_port);
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (::bind(socket, reinterpret_cast<sockaddr *>(&address), sizeof(address)) != 0 ||
        ::listen(socket, 16) != 0) {
        close(socket);
        return kInvalidSocket;
    }

    sockaddr_in bound{};
#if defined(_WIN32)
    int length = sizeof(bound);
#else
    socklen_t length = sizeof(bound);
#endif
    if (getsockname(socket, reinterpret_cast<sockaddr *>(&bound), &length) != 0) {
        close(socket);
        return kInvalidSocket;
    }
    actual_port = ntohs(bound.sin_port);
    return socket;
}

} // namespace orbit3d::net
