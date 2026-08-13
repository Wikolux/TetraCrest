from app.services.ai.runtime.cancellation import CancellationToken


def test_token_starts_uncancelled():
    assert CancellationToken().cancelled() is False


def test_cancel_marks_the_token_cancelled():
    token = CancellationToken()

    token.cancel()

    assert token.cancelled() is True


def test_cancel_is_idempotent():
    token = CancellationToken()

    token.cancel()
    token.cancel()

    assert token.cancelled() is True


def test_two_tokens_are_independent():
    first, second = CancellationToken(), CancellationToken()

    first.cancel()

    assert first.cancelled() is True
    assert second.cancelled() is False


def test_cancellation_is_visible_through_a_shared_reference():
    token = CancellationToken()
    alias = token

    alias.cancel()

    assert token.cancelled() is True
