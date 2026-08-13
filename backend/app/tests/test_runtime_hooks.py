from app.services.ai.providers.enums import ProviderName
from app.services.ai.runtime.hooks import RuntimeHook
from app.services.ai.runtime.types import RuntimeContext, RuntimeRequest, RuntimeResponse
from app.services.prompt_builder.types import PromptPackage


def _request():
    return RuntimeRequest(
        organization_id=1, prompt_package=PromptPackage(system_prompt="s"), provider=ProviderName.OPENAI
    )


def test_runtime_hook_can_be_instantiated_directly_as_a_no_op():
    # not an ABC - a plain RuntimeHook() is a valid, fully-functional
    # no-op hook, unlike KernelHook which is abstract
    hook = RuntimeHook()

    assert isinstance(hook, RuntimeHook)


def test_default_before_execution_returns_none():
    assert RuntimeHook().before_execution(RuntimeContext(), _request()) is None


def test_default_after_execution_returns_none():
    response = RuntimeResponse(success=True)

    assert RuntimeHook().after_execution(RuntimeContext(), response) is None


def test_default_on_error_returns_none():
    assert RuntimeHook().on_error(RuntimeContext(), ValueError("boom")) is None


def test_default_on_cancel_returns_none():
    assert RuntimeHook().on_cancel(RuntimeContext()) is None


def test_default_on_timeout_returns_none():
    assert RuntimeHook().on_timeout(RuntimeContext()) is None


def test_a_hook_can_override_only_the_one_method_it_cares_about():
    class _AfterOnlyHook(RuntimeHook):
        def __init__(self):
            self.seen = []

        def after_execution(self, context, response):
            self.seen.append(response)

    hook = _AfterOnlyHook()
    context = RuntimeContext()
    response = RuntimeResponse(success=True)

    # every other method still works via the inherited no-op default
    hook.before_execution(context, _request())
    hook.on_error(context, ValueError("boom"))
    hook.on_cancel(context)
    hook.on_timeout(context)
    hook.after_execution(context, response)

    assert hook.seen == [response]
