import pytest

from app.services.ai.shared.exceptions import (
    AIError,
    AIProviderError,
    AuthenticationError,
    ContentFilterError,
    InvalidRequestError,
    ModelNotFoundError,
    ProviderUnavailableError,
    QuotaExceededError,
    RateLimitError,
    StreamingError,
)
from app.services.ai.shared.exceptions import TimeoutError as AITimeoutError

_ALL_SUBCLASSES = [
    AIProviderError,
    AuthenticationError,
    RateLimitError,
    AITimeoutError,
    ProviderUnavailableError,
    InvalidRequestError,
    ContentFilterError,
    QuotaExceededError,
    ModelNotFoundError,
    StreamingError,
]


def test_ai_error_is_an_exception():
    assert issubclass(AIError, Exception)


@pytest.mark.parametrize("error_class", _ALL_SUBCLASSES)
def test_every_normalized_error_inherits_from_ai_error(error_class):
    assert issubclass(error_class, AIError)


@pytest.mark.parametrize("error_class", _ALL_SUBCLASSES)
def test_every_normalized_error_can_be_raised_and_caught_as_ai_error(error_class):
    with pytest.raises(AIError):
        raise error_class("boom")


@pytest.mark.parametrize("error_class", _ALL_SUBCLASSES)
def test_every_normalized_error_carries_its_message(error_class):
    error = error_class("something went wrong")

    assert str(error) == "something went wrong"


def test_ai_provider_error_can_still_be_caught_specifically():
    # backward compatibility: existing code catching AIProviderError
    # specifically (not the broader AIError) must keep working
    with pytest.raises(AIProviderError):
        raise AIProviderError("unsupported provider")


def test_catching_ai_error_catches_every_subclass_generically():
    for error_class in _ALL_SUBCLASSES:
        try:
            raise error_class("boom")
        except AIError as caught:
            assert isinstance(caught, error_class)
        else:
            pytest.fail(f"{error_class.__name__} was not caught by AIError")


def test_error_classes_are_all_distinct_types():
    assert len(set(_ALL_SUBCLASSES)) == len(_ALL_SUBCLASSES)


def test_ai_timeout_error_does_not_replace_the_builtin_timeout_error():
    assert AITimeoutError is not TimeoutError
    assert issubclass(AITimeoutError, AIError)
    assert not issubclass(TimeoutError, AIError)
