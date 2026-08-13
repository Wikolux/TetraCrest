"""Type aliases shared by the execution_context/execution_metadata pair.

A separate leaf module (rather than folding this into execution_context.py)
so execution_metadata.py can depend on the same Metadata alias without
importing execution_context.py itself - the two value-object modules stay
siblings, neither one a prerequisite for the other.
"""

from typing import Any, Mapping

Metadata = Mapping[str, Any]
