#include "orbit3d/orbit3d.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    orbit3d_client *client = NULL;
    orbit3d_device_info devices[ORBIT3D_MAX_DEVICES];
    size_t device_count = 0;
    orbit3d_event event;
    int saw_motion = 0;
    int saw_button = 0;
    int attempt;

    if (argc != 2) {
        fprintf(stderr, "Usage: orbit3d_c_sdk_smoke PORT\n");
        return 2;
    }

    if (orbit3d_connect("127.0.0.1", (uint16_t)strtoul(argv[1], NULL, 10), &client) != ORBIT3D_OK) {
        fprintf(stderr, "Could not connect to OrbitHub\n");
        return 1;
    }
    if (orbit3d_list_devices(client, devices, ORBIT3D_MAX_DEVICES, &device_count) != ORBIT3D_OK ||
        device_count != 1 || devices[0].button_count != 4) {
        fprintf(stderr, "Unexpected simulated device\n");
        orbit3d_disconnect(client);
        return 1;
    }
    if (orbit3d_subscribe(client, ORBIT3D_SUBSCRIBE_MOTION | ORBIT3D_SUBSCRIBE_BUTTONS) !=
        ORBIT3D_OK) {
        fprintf(stderr, "Could not subscribe\n");
        orbit3d_disconnect(client);
        return 1;
    }

    for (attempt = 0; attempt < 100 && !(saw_motion && saw_button); ++attempt) {
        const orbit3d_result result = orbit3d_poll(client, &event, 100);
        if (result == ORBIT3D_TIMEOUT) {
            continue;
        }
        if (result != ORBIT3D_OK) {
            fprintf(stderr, "Polling failed: %s\n", orbit3d_result_string(result));
            orbit3d_disconnect(client);
            return 1;
        }
        saw_motion = saw_motion || event.type == ORBIT3D_EVENT_MOTION;
        saw_button = saw_button || event.type == ORBIT3D_EVENT_BUTTON;
    }

    orbit3d_disconnect(client);
    if (!saw_motion || !saw_button) {
        fprintf(stderr, "Expected motion and button events\n");
        return 1;
    }
    printf("C SDK smoke test passed\n");
    return 0;
}
