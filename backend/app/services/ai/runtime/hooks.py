from app.services.ai.runtime.types import RuntimeContext, RuntimeRequest, RuntimeResponse


class RuntimeHook:
    """Observes an execution's lifecycle: before/after the whole
    execution, on error, on cancel, and on timeout.

    Every method is concrete with a no-op default, not abstract -
    deliberately different from app.services.ai.kernel.hooks.KernelHook
    (whose 3 methods are all abstract). This package has 5 hook points;
    forcing every hook implementation to stub 4 empty methods just to
    observe the one it actually cares about is real, avoidable friction a
    fully-abstract contract doesn't justify here. Future agents can
    subscribe by overriding only the methods they need.

    Not an ABC: there is no member every subclass MUST implement to be
    useful, so the class itself is instantiable as a true no-op hook.
    """

    def before_execution(self, context: RuntimeContext, request: RuntimeRequest) -> None:
        return None

    def after_execution(self, context: RuntimeContext, response: RuntimeResponse) -> None:
        return None

    def on_error(self, context: RuntimeContext, error: Exception) -> None:
        return None

    def on_cancel(self, context: RuntimeContext) -> None:
        return None

    def on_timeout(self, context: RuntimeContext) -> None:
        return None
