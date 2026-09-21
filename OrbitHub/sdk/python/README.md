# Orbit3D Python SDK

Python clients and hardware providers for the Orbit3D 0.2 protocol.
Requires Python 3.10+ and a running OrbitHub broker.

```python
from orbit3d_hub import Client

with Client() as client:
    for device in client.list_devices():
        print(device.vendor, device.product, device.serial)
```

`Client` receives input. `Provider` publishes device input. `InputState` holds
motion and ordered button events for one selected device. The SDK uses only
the Python standard library and does not start the broker.
