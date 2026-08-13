from app.services.ai.kernel.hooks import KernelHook
from app.services.ai.kernel.middleware import KernelMiddleware


class RuntimeRegistry:
    """Holds the middleware, hooks, and capability runtimes one KernelRuntime uses.

    Deliberately instance-level state, not class-level/global: each
    RuntimeRegistry is its own object, constructed with `RuntimeRegistry()`.
    Two instances never share registrations, so multiple KernelRuntimes -
    one per test, one per environment, one per tenant in some future
    design - can never leak state into each other. This is unlike
    ConversationProviderRegistry (app.services.ai.conversation.registry),
    which deliberately uses class-level state for that simpler,
    single-purpose registry - the kernel explicitly avoids that pattern
    per this milestone's "no global state, no singleton" requirement.

    Provider registration is intentionally out of scope: providers
    register with their own capability-specific registry (e.g.
    ConversationProviderRegistry) elsewhere - never here.
    """

    def __init__(self) -> None:
        self._middleware: list[KernelMiddleware] = []
        self._hooks: list[KernelHook] = []
        self._capability_runtimes: dict[str, object] = {}

    def register_middleware(self, middleware: KernelMiddleware) -> None:
        self._middleware.append(middleware)

    def register_hook(self, hook: KernelHook) -> None:
        self._hooks.append(hook)

    def register_capability_runtime(self, capability: str, runtime: object) -> None:
        """Associate a capability name with whatever object represents
        its runtime. `runtime` is deliberately untyped (`object`) - the
        kernel has no opinion about what a capability runtime looks like,
        only that one can be looked up by capability name.
        """
        self._capability_runtimes[capability] = runtime

    def get_middleware(self) -> tuple[KernelMiddleware, ...]:
        """Registered middleware, in registration order. A tuple, not the
        internal list - the caller can never mutate what's registered
        through the return value."""
        return tuple(self._middleware)

    def get_hooks(self) -> tuple[KernelHook, ...]:
        """Registered hooks, in registration order. A tuple, not the
        internal list - the caller can never mutate what's registered
        through the return value."""
        return tuple(self._hooks)

    def get_capability_runtime(self, capability: str) -> object | None:
        return self._capability_runtimes.get(capability)
