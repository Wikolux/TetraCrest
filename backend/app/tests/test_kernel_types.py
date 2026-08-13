import pytest

from app.services.ai.kernel.types import KernelError, Metadata, Payload


def test_kernel_error_is_an_exception():
    assert issubclass(KernelError, Exception)


def test_kernel_error_can_be_raised_and_caught():
    with pytest.raises(KernelError, match="boom"):
        raise KernelError("boom")


def test_kernel_error_carries_a_message():
    error = KernelError("something went wrong")

    assert str(error) == "something went wrong"


def test_metadata_and_payload_type_aliases_exist():
    # these are type aliases, not runtime-checkable classes - just confirm
    # they're importable and usable as annotations
    assert Metadata is not None
    assert Payload is not None
