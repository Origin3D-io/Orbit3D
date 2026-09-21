#pragma once

#include "adapter.hpp"

#include <atomic>
#include <thread>

namespace orbit3d::hub {

class SimulatorAdapter final : public DeviceAdapter {
  public:
    ~SimulatorAdapter() override;
    bool start(AdapterSink &sink) override;
    void stop() override;

  private:
    void run();

    AdapterSink *sink_{};
    std::atomic<bool> running_{false};
    std::thread thread_;
};

} // namespace orbit3d::hub
