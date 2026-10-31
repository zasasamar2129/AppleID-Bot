"""Make the bridge package importable when pytest runs from the repo root.

The repository root also contains an ``app/`` package (the Telegram bot), so
the bridge deliberately names its package ``bridge_app`` to avoid any
ambiguity. This conftest only needs to put the bridge directory on ``sys.path``
so ``import bridge_app`` resolves.
"""

import os
import sys

_BRIDGE_ROOT = os.path.dirname(os.path.abspath(__file__))

if _BRIDGE_ROOT not in sys.path:
    sys.path.insert(0, _BRIDGE_ROOT)

os.environ.setdefault("BRIDGE_API_KEY", "test_secret_key")
os.environ.setdefault("SEP_MERCHANT_ID", "12345")
