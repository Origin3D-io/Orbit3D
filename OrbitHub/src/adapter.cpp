#include "adapter.hpp"

#include <chrono>

namespace orbit3d::hub {

std::uint64_t monotonic_timestamp_us() {
    return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::microseconds>(
                                          std::chrono::steady_clock::now().time_since_epoch())
                                          .count());
}

} // namespace orbit3d::hub
