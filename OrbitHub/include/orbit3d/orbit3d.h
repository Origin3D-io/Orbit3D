#pragma once

#include <stddef.h>
#include <stdint.h>

#if defined(ORBIT3D_STATIC)
#define ORBIT3D_API
#elif defined(_WIN32) && defined(ORBIT3D_SDK_BUILD)
#define ORBIT3D_API __declspec(dllexport)
#elif defined(_WIN32)
#define ORBIT3D_API __declspec(dllimport)
#else
#define ORBIT3D_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define ORBIT3D_SDK_VERSION_MAJOR 0
#define ORBIT3D_SDK_VERSION_MINOR 2
#define ORBIT3D_MAX_TEXT 96
#define ORBIT3D_MAX_DEVICES 32

typedef struct orbit3d_client orbit3d_client;

typedef enum orbit3d_result {
    ORBIT3D_OK = 0,
    ORBIT3D_TIMEOUT = 1,
    ORBIT3D_DISCONNECTED = 2,
    ORBIT3D_INVALID_ARGUMENT = 3,
    ORBIT3D_PROTOCOL_ERROR = 4,
    ORBIT3D_IO_ERROR = 5,
    ORBIT3D_BUFFER_TOO_SMALL = 6,
} orbit3d_result;

typedef enum orbit3d_event_type {
    ORBIT3D_EVENT_NONE = 0,
    ORBIT3D_EVENT_MOTION = 1,
    ORBIT3D_EVENT_BUTTON = 2,
    ORBIT3D_EVENT_DEVICE = 3,
    ORBIT3D_EVENT_BUTTON_STATE = 4,
} orbit3d_event_type;

typedef enum orbit3d_subscription {
    ORBIT3D_SUBSCRIBE_MOTION = 1U << 0,
    ORBIT3D_SUBSCRIBE_BUTTONS = 1U << 1,
    ORBIT3D_SUBSCRIBE_DEVICES = 1U << 2,
} orbit3d_subscription;

typedef struct orbit3d_device_info {
    uint32_t device_id;
    uint32_t capabilities;
    uint8_t connected;
    uint8_t button_count;
    char vendor[ORBIT3D_MAX_TEXT];
    char product[ORBIT3D_MAX_TEXT];
    char serial[ORBIT3D_MAX_TEXT];
} orbit3d_device_info;

typedef struct orbit3d_motion_event {
    uint32_t device_id;
    uint64_t timestamp_us;
    int32_t tx;
    int32_t ty;
    int32_t tz;
    int32_t rx;
    int32_t ry;
    int32_t rz;
} orbit3d_motion_event;

typedef struct orbit3d_button_event {
    uint32_t device_id;
    uint64_t timestamp_us;
    uint16_t button_id;
    uint8_t pressed;
} orbit3d_button_event;

typedef struct orbit3d_device_event {
    uint32_t device_id;
    uint8_t connected;
} orbit3d_device_event;

typedef struct orbit3d_event {
    orbit3d_event_type type;
    union {
        orbit3d_motion_event motion;
        orbit3d_button_event button;
        orbit3d_device_event device;
        struct {
            uint32_t device_id;
            uint32_t buttons;
        } button_state;
    } data;
} orbit3d_event;

ORBIT3D_API orbit3d_result orbit3d_connect(const char *host, uint16_t port,
                                           orbit3d_client **out_client);

ORBIT3D_API void orbit3d_disconnect(orbit3d_client *client);

ORBIT3D_API orbit3d_result orbit3d_list_devices(orbit3d_client *client,
                                                orbit3d_device_info *devices, size_t capacity,
                                                size_t *out_count);

ORBIT3D_API orbit3d_result orbit3d_subscribe(orbit3d_client *client, uint32_t subscriptions);

ORBIT3D_API orbit3d_result orbit3d_poll(orbit3d_client *client, orbit3d_event *event,
                                        uint32_t timeout_ms);

ORBIT3D_API const char *orbit3d_result_string(orbit3d_result result);

#ifdef __cplusplus
}
#endif
