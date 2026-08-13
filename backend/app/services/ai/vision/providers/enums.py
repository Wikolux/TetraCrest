"""Vision providers are identified by the exact same ProviderName every
other AI Platform capability uses - re-exported here (never redefined)
so vision/ code has its own local import surface without duplicating the
enum. "Do not duplicate any of these" applies to provider identity the
same way it applies to SharedExecutionContext, ExecutionMetrics, etc.
"""

from app.services.ai.providers.enums import ProviderName

__all__ = ["ProviderName"]
