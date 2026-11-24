"""Direct-mode test setup.

Fixtures (direct_vm, direct_deploy, direct_alice, direct_bob, ...) are
provided by the ``genlayer-test`` pytest plugin — see requirements.txt.
``to_hex`` mirrors the GenLayer boilerplate helper: contract methods
return ``Address`` objects whose ``as_hex`` is an EIP-55 checksummed
hex string, and test accounts are raw bytes.
"""


def to_hex(addr_bytes):
    """Convert address bytes to checksummed hex matching contract output."""
    if hasattr(addr_bytes, "as_hex"):
        return addr_bytes.as_hex
    from genlayer.py.types import Address

    return Address(addr_bytes).as_hex
