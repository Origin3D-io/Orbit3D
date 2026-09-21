# Service lifecycle

OrbitHub, hardware providers, and application consumers are separate processes.
The broker distributes input but does not open devices or manage provider startup.

## Providers

A provider connects, registers its devices, and publishes motion and button
events. It must send input or ping at least once per second. Three seconds of
inactivity removes its registrations. A closed connection also removes its
devices and releases held buttons.

The provider must remain running for its devices to produce input. Closing a
control window and exiting the provider process are distinct lifecycle actions.
The host product decides whether window closure leaves a provider running.

After a broker restart, providers reconnect and register again. Runtime device
IDs may change; consumers must refresh discovery rather than reuse old IDs.

## Consumers

Applications clear input when a selected device disconnects, reconnect after
transport failure, and repeat subscription and discovery. The broker's continued
availability does not imply that a particular provider is running.

Applications must stop motion after 250 ms without a fresh sample, independently
of provider connection state. A live connection alone is not fresh motion.

## Deployment

The runtime may be packaged with a provider or managed separately. Login startup,
OS service installation, and updates belong to the deployment layer. They are
not performed by the SDK. See [deployment requirements](../../docs/compatibility.md).
