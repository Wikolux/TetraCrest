from app.services.ai.kernel.hooks import KernelHook
from app.services.ai.kernel.middleware import KernelMiddleware
from app.services.ai.kernel.registry import RuntimeRegistry


class _FakeMiddleware(KernelMiddleware):
    def before_execute(self, request):
        return request

    def after_execute(self, request, response):
        return response

    def on_error(self, request, error):
        return None


class _FakeHook(KernelHook):
    def before_execution(self, request):
        return None

    def after_execution(self, request, response):
        return None

    def execution_failed(self, request, error):
        return None


def test_registry_starts_empty():
    registry = RuntimeRegistry()

    assert registry.get_middleware() == ()
    assert registry.get_hooks() == ()


def test_register_and_retrieve_middleware():
    registry = RuntimeRegistry()
    middleware = _FakeMiddleware()

    registry.register_middleware(middleware)

    assert registry.get_middleware() == (middleware,)


def test_register_and_retrieve_hook():
    registry = RuntimeRegistry()
    hook = _FakeHook()

    registry.register_hook(hook)

    assert registry.get_hooks() == (hook,)


def test_middleware_registered_in_order():
    registry = RuntimeRegistry()
    first, second = _FakeMiddleware(), _FakeMiddleware()

    registry.register_middleware(first)
    registry.register_middleware(second)

    assert registry.get_middleware() == (first, second)


def test_hooks_registered_in_order():
    registry = RuntimeRegistry()
    first, second = _FakeHook(), _FakeHook()

    registry.register_hook(first)
    registry.register_hook(second)

    assert registry.get_hooks() == (first, second)


def test_get_middleware_returns_a_tuple_not_the_internal_list():
    registry = RuntimeRegistry()
    registry.register_middleware(_FakeMiddleware())

    assert isinstance(registry.get_middleware(), tuple)


def test_register_and_retrieve_capability_runtime():
    registry = RuntimeRegistry()
    runtime = object()

    registry.register_capability_runtime("conversation", runtime)

    assert registry.get_capability_runtime("conversation") is runtime


def test_get_capability_runtime_returns_none_when_unregistered():
    registry = RuntimeRegistry()

    assert registry.get_capability_runtime("vision") is None


def test_registry_has_no_provider_registration_api():
    registry = RuntimeRegistry()

    assert not hasattr(registry, "register_provider")
    assert not hasattr(registry, "get_provider")


# --- registry isolation between tests / instances -----------------------------


def test_two_registry_instances_never_share_state():
    first = RuntimeRegistry()
    second = RuntimeRegistry()

    first.register_middleware(_FakeMiddleware())
    first.register_hook(_FakeHook())
    first.register_capability_runtime("conversation", object())

    assert second.get_middleware() == ()
    assert second.get_hooks() == ()
    assert second.get_capability_runtime("conversation") is None


def test_registry_is_not_class_level_shared_state():
    # RuntimeRegistry deliberately holds no class-level mutable
    # collections - registering on one instance must never affect a
    # brand-new instance of the same class
    first = RuntimeRegistry()
    first.register_middleware(_FakeMiddleware())

    assert RuntimeRegistry().get_middleware() == ()
