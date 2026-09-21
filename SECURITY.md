# Security

OrbitHub uses a local TCP endpoint. Its current trust boundary is the workstation,
not an authenticated user or provider.

The broker binds to IPv4 loopback only. It has no authentication, encryption, or
per-user endpoint access control. Another local process can publish input,
subscribe to input, impersonate device metadata, or occupy the broker port.
The `OrbitHub` hello string is a protocol check, not proof of identity.

Do not expose or forward the port to a network. Do not use device identity as
authorization. The broker must not run with administrator/root privileges.

Current limits: 64 connections, 32 devices, 64 KiB payloads, bounded consumer
queues, partial-packet deadlines, and provider liveness expiry. These are not a
substitute for authentication, fuzzing, or a security review.

Local programs are trusted by design. Consumers and providers do not need
credentials or approval to connect. Deployments requiring user or application
isolation must add that boundary before use.

Report security issues privately to [contact@origin3d.io](mailto:contact@origin3d.io).
Include the affected version, platform, and steps to reproduce. Do not post
exploit details or sensitive data in a public issue.
