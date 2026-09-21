#include "orbit3d/orbit3d.hpp"

#include <cstdint>
#include <cstdlib>
#include <iostream>

int main(int argc, char **argv) {
    if (argc != 2) {
        std::cerr << "Usage: orbit3d_sdk_smoke PORT\n";
        return 2;
    }

    try {
        orbit3d::Client client("127.0.0.1",
                               static_cast<std::uint16_t>(std::strtoul(argv[1], nullptr, 10)));
        const auto devices = client.devices();
        if (devices.size() != 1 || devices[0].button_count != 4) {
            std::cerr << "Unexpected simulated device\n";
            return 1;
        }

        client.subscribe(ORBIT3D_SUBSCRIBE_MOTION | ORBIT3D_SUBSCRIBE_BUTTONS);
        bool saw_motion = false;
        bool saw_button = false;
        for (int attempt = 0; attempt < 100 && !(saw_motion && saw_button); ++attempt) {
            orbit3d_event event{};
            const auto result = client.poll(event, 100);
            if (result == ORBIT3D_TIMEOUT) {
                continue;
            }
            if (result != ORBIT3D_OK) {
                throw orbit3d::Error(result);
            }
            saw_motion = saw_motion || event.type == ORBIT3D_EVENT_MOTION;
            saw_button = saw_button || event.type == ORBIT3D_EVENT_BUTTON;
        }

        if (!saw_motion || !saw_button) {
            std::cerr << "Expected motion and button events\n";
            return 1;
        }
        std::cout << "C++ SDK smoke test passed\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
