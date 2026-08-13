from app.services.ai.tools.hooks import ToolHook


def test_tool_hook_can_be_instantiated_directly_as_a_no_op():
    hook = ToolHook()

    assert isinstance(hook, ToolHook)


def test_default_before_validation_returns_none():
    assert ToolHook().before_validation(None, None) is None


def test_default_after_validation_returns_none():
    assert ToolHook().after_validation(None, None) is None


def test_default_before_execution_returns_none():
    assert ToolHook().before_execution(None, None) is None


def test_default_after_execution_returns_none():
    assert ToolHook().after_execution(None, None) is None


def test_default_on_failure_returns_none():
    assert ToolHook().on_failure(None, ValueError("boom")) is None


def test_default_on_cancel_returns_none():
    assert ToolHook().on_cancel(None) is None


def test_a_hook_can_override_only_the_one_method_it_cares_about():
    class _AfterOnlyHook(ToolHook):
        def __init__(self):
            self.seen = []

        def after_execution(self, context, result):
            self.seen.append(result)

    hook = _AfterOnlyHook()

    hook.before_validation(None, None)
    hook.before_execution(None, None)
    hook.after_execution("context", "result")

    assert hook.seen == ["result"]
