"""GenericProviderRegistry - the canonical provider/class registry for the
whole AI Operating System.

Introduced during the Vision Framework milestone (M19) after noticing the
same registry shape - class-level dict, threading.RLock, duplicate-
registration rejection unless overwrite=True, register/unregister/clear/
get/is_registered/all_registered - had already been hand-copied across
ConversationProviderRegistry, AgentRegistry, ToolRegistry, and
SpecialistRegistry before Vision needed it four more times (one per
capability: image/document/extraction/analysis). Rather than copy it an
eighth time, this generic base is what every registry in the platform now
builds on by subclassing - Conversation/Agent/Specialist/Tool registries
included (the M19 completion pass migrated them here without changing
their public method surface, constructor signatures, or exception types).

Subclassing (not instantiating) is what gives each concrete registry its
own independent `_providers` dict and lock: __init_subclass__ allocates a
fresh dict/lock on every subclass at class-definition time, since class
attributes would otherwise be shared across every subclass through the
base class.

Registries whose entries need extra registration-time metadata (ToolRegistry's
name/category/capabilities/permissions, SpecialistRegistry's specialization/
supported_tasks) still subclass this directly - TValue is simply a small
frozen "Registration" dataclass instead of a bare provider class, and the
subclass adds its own register()/get() overrides plus whatever aggregate
query methods (categories(), specializations(), ...) its domain needs.
kernel.registry.RuntimeRegistry is deliberately NOT one of these: it holds
per-instance middleware/hooks/capability-runtime state (never class-level,
per the Kernel's explicit "no global state" requirement), an entirely
different concept from "map a key to a registered class," so it is not a
duplicate of this and is left as-is.
"""

import threading
from typing import Generic, TypeVar

TKey = TypeVar("TKey")
TValue = TypeVar("TValue")


class GenericProviderRegistry(Generic[TKey, TValue]):
    _providers: dict = {}
    _lock = threading.RLock()
    _registration_error: type[Exception] = ValueError

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        cls._providers = {}
        cls._lock = threading.RLock()

    @classmethod
    def register(cls, key: TKey, value: TValue, *, overwrite: bool = False) -> None:
        with cls._lock:
            if key in cls._providers and not overwrite:
                raise cls._registration_error(
                    f"'{key}' is already registered. Pass overwrite=True to replace it explicitly."
                )
            cls._providers[key] = value

    @classmethod
    def unregister(cls, key: TKey) -> None:
        """Remove a registration if present. Never raises for a key that
        isn't registered."""
        with cls._lock:
            cls._providers.pop(key, None)

    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls._providers.clear()

    @classmethod
    def get(cls, key: TKey) -> TValue | None:
        with cls._lock:
            return cls._providers.get(key)

    @classmethod
    def is_registered(cls, key: TKey) -> bool:
        with cls._lock:
            return key in cls._providers

    @classmethod
    def all_registered(cls) -> dict:
        """Return a copy of the registry - mutating the returned dict
        never affects what's actually registered."""
        with cls._lock:
            return dict(cls._providers)
