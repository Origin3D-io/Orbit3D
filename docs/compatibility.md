# Compatibility

Protocol **0.2** requires matching runtime and SDK major/minor versions.
Mismatched connections are rejected.

| SDK | Application input | Hardware provider |
| --- | --- | --- |
| C / C++ | Available | Use the wire protocol |
| Python | Available | Available |

The device manufacturer's control application normally launches OrbitHub and
its provider. A host product may instead manage them as separate local processes.
The installer or host product owns startup, updates, and process lifetime.
The SDK connects to an already-running broker.

Example integrations include the Python SDK and require a running broker and provider.
See [Security](../SECURITY.md) for the local trust boundary.

## Versions

Protocol 0.2 controls wire compatibility. Runtime, SDK, and addon releases are
versioned separately; each addon archive bundles its matching SDK.
See [Changelog](../CHANGELOG.md).

`InputState.reset()` emits `InputReset`. Consumers clear held-button state
without executing commands when they receive this event.

The hello response identifies the protocol and supported roles. Use
`orbithub --version` for the runtime build.
