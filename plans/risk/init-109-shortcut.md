# INIT-109 Risk Gate: Shortcut

Verdict: LOW

The local runner could have become a shortcut if presented as Buildkite itself.
The proposal avoids that by naming it a local emulator, limiting supported step
types, and rejecting unsupported constructs. The real Buildkite agent still
exists as raw manifests and uses the documented token flow.

No shortcut risk blocks implementation.
