from app.services.ai.vision.shared.exceptions import VisionError, VisionExecutionError, VisionProviderError


def test_vision_error_is_an_exception():
    assert issubclass(VisionError, Exception)


def test_vision_provider_error_is_a_vision_error():
    assert issubclass(VisionProviderError, VisionError)


def test_vision_execution_error_is_a_vision_error():
    assert issubclass(VisionExecutionError, VisionError)


def test_vision_error_can_be_raised_and_caught():
    try:
        raise VisionProviderError("boom")
    except VisionError as exc:
        assert str(exc) == "boom"
