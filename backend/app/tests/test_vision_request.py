import dataclasses
from types import MappingProxyType

import pytest

from app.services.ai.runtime.cancellation import CancellationToken
from app.services.ai.shared.execution_context import SharedExecutionContext
from app.services.ai.vision.providers.enums import ProviderName
from app.services.ai.vision.request import VisionInput, VisionInputKind, VisionRequest


def _image_input(**overrides):
    defaults = dict(kind=VisionInputKind.IMAGE, bytes_data=b"fake-bytes")
    defaults.update(overrides)
    return VisionInput(**defaults)


# --- VisionInput --------------------------------------------------------------------


def test_vision_input_with_bytes_data():
    vision_input = VisionInput(kind=VisionInputKind.IMAGE, bytes_data=b"data")

    assert vision_input.bytes_data == b"data"
    assert vision_input.path is None
    assert vision_input.url is None


def test_vision_input_with_path():
    vision_input = VisionInput(kind=VisionInputKind.DOCUMENT, path="/tmp/file.pdf")

    assert vision_input.path == "/tmp/file.pdf"


def test_vision_input_with_url():
    vision_input = VisionInput(kind=VisionInputKind.IMAGE, url="https://example.com/image.png")

    assert vision_input.url == "https://example.com/image.png"


def test_vision_input_requires_exactly_one_source():
    with pytest.raises(ValueError, match="exactly one"):
        VisionInput(kind=VisionInputKind.IMAGE)


def test_vision_input_rejects_multiple_sources():
    with pytest.raises(ValueError, match="exactly one"):
        VisionInput(kind=VisionInputKind.IMAGE, bytes_data=b"data", path="/tmp/x.png")


def test_vision_input_metadata_cannot_be_mutated():
    vision_input = _image_input(metadata={"a": 1})

    with pytest.raises(TypeError):
        vision_input.metadata["a"] = 2


def test_vision_input_is_frozen():
    vision_input = _image_input()

    with pytest.raises(dataclasses.FrozenInstanceError):
        vision_input.path = "/tmp/x"


# --- VisionRequest -------------------------------------------------------------------


def test_defaults():
    request = VisionRequest(inputs=(_image_input(),), capability_category="image")

    assert request.provider == ProviderName.UNKNOWN
    assert request.objective == ""
    assert request.stream is False
    assert request.cancellation_token is None
    assert request.parent_shared is None
    assert isinstance(request.shared, SharedExecutionContext)


def test_inputs_is_coerced_to_a_tuple():
    request = VisionRequest(inputs=[_image_input()], capability_category="image")

    assert isinstance(request.inputs, tuple)


def test_requires_at_least_one_input():
    with pytest.raises(ValueError, match="at least one input"):
        VisionRequest(inputs=(), capability_category="image")


def test_supports_multiple_inputs_not_assuming_a_single_image():
    inputs = (_image_input(), _image_input(bytes_data=b"second"))

    request = VisionRequest(inputs=inputs, capability_category="image")

    assert len(request.inputs) == 2


def test_construction_with_all_fields():
    token = CancellationToken()
    shared = SharedExecutionContext(organization_id=1)
    parent = SharedExecutionContext()

    request = VisionRequest(
        inputs=(_image_input(),),
        capability_category="document",
        shared=shared,
        provider=ProviderName.ANTHROPIC,
        objective="describe this",
        stream=True,
        cancellation_token=token,
        parent_shared=parent,
    )

    assert request.capability_category == "document"
    assert request.shared is shared
    assert request.provider == ProviderName.ANTHROPIC
    assert request.objective == "describe this"
    assert request.stream is True
    assert request.cancellation_token is token
    assert request.parent_shared is parent


def test_metadata_defaults_to_empty_read_only_mapping():
    request = VisionRequest(inputs=(_image_input(),), capability_category="image")

    assert isinstance(request.metadata, MappingProxyType)


def test_metadata_cannot_be_mutated():
    request = VisionRequest(inputs=(_image_input(),), capability_category="image", metadata={"a": 1})

    with pytest.raises(TypeError):
        request.metadata["a"] = 2


def test_is_frozen():
    request = VisionRequest(inputs=(_image_input(),), capability_category="image")

    with pytest.raises(dataclasses.FrozenInstanceError):
        request.objective = "changed"
