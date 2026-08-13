from app.services.ai.vision.hooks import VisionHook


def test_vision_hook_can_be_instantiated_directly_as_a_no_op():
    hook = VisionHook()

    assert isinstance(hook, VisionHook)


def test_default_before_analysis_returns_none():
    assert VisionHook().before_analysis(None, None) is None


def test_default_after_analysis_returns_none():
    assert VisionHook().after_analysis(None, None) is None


def test_default_on_failure_returns_none():
    assert VisionHook().on_failure(None, ValueError("boom")) is None


def test_default_on_timeout_returns_none():
    assert VisionHook().on_timeout(None) is None


def test_default_on_cancel_returns_none():
    assert VisionHook().on_cancel(None) is None


def test_a_hook_can_override_only_the_one_method_it_cares_about():
    class _AfterOnlyHook(VisionHook):
        def __init__(self):
            self.seen = []

        def after_analysis(self, context, response):
            self.seen.append(response)

    hook = _AfterOnlyHook()

    hook.before_analysis(None, None)
    hook.on_failure(None, ValueError("boom"))
    hook.on_timeout(None)
    hook.on_cancel(None)
    hook.after_analysis("context", "response")

    assert hook.seen == ["response"]
