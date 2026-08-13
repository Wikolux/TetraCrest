import pytest

from app.services.ai.runtime.timeout import RuntimeTimeout, RuntimeTimeoutError
from app.services.ai.runtime.types import AIRuntimeError


def test_runtime_timeout_error_is_an_ai_runtime_error():
    assert issubclass(RuntimeTimeoutError, AIRuntimeError)


def test_none_seconds_means_no_timeout_is_enforced():
    result = RuntimeTimeout(None).run(lambda: "done")

    assert result == "done"


def test_run_returns_the_callables_result_when_within_the_timeout():
    result = RuntimeTimeout(10).run(lambda: "done")

    assert result == "done"


def test_run_passes_through_args_and_kwargs():
    result = RuntimeTimeout(10).run(lambda a, b, c=0: a + b + c, 1, 2, c=3)

    assert result == 6


def test_run_raises_runtime_timeout_error_when_the_call_takes_too_long():
    import time

    with pytest.raises(RuntimeTimeoutError):
        RuntimeTimeout(0.01).run(lambda: time.sleep(0.05))


def test_a_raised_exception_from_the_wrapped_call_propagates_unchanged():
    def _boom():
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        RuntimeTimeout(10).run(_boom)
