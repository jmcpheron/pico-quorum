# Rebuild a Safe transaction hash on the device from the fields shown on screen. The console never
# signs a digest it was handed: it hashes these fields itself, and if the transaction service's
# safeTxHash differs, the service is lying about what it wants signed and the console refuses.
# Safe >= 1.3.0: the EIP-712 domain is {chainId, verifyingContract}, no name or version.
# Every change here must pass test-vectors/run.py.
from keccak import keccak256

DOMAIN_TYPEHASH = keccak256(b"EIP712Domain(uint256 chainId,address verifyingContract)")
SAFE_TX_TYPEHASH = keccak256(b"SafeTx(address to,uint256 value,bytes data,uint8 operation,uint256 safeTxGas,"
                             b"uint256 baseGas,uint256 gasPrice,address gasToken,address refundReceiver,uint256 nonce)")
ZERO = "0x0000000000000000000000000000000000000000"
CALL, DELEGATECALL = 0, 1

_domain_cache = {}


def _hex(h):
    return bytes.fromhex(h[2:] if h.startswith("0x") else h)


def _addr(a):
    b = _hex(a)
    if len(b) != 20:
        raise ValueError("address must be 20 bytes")
    return bytes(12) + b


def _u256(n):
    n = int(n)
    if n < 0 or n >> 256:
        raise ValueError("uint256 out of range")
    return n.to_bytes(32, "big")


def domain_separator(chain_id, safe):
    key = (int(chain_id), safe.lower())
    if key not in _domain_cache:
        _domain_cache[key] = keccak256(DOMAIN_TYPEHASH + _u256(chain_id) + _addr(safe))
    return _domain_cache[key]


def message_hash(to, value, data, operation, safe_tx_gas=0, base_gas=0, gas_price=0, gas_token=ZERO,
                 refund_receiver=ZERO, nonce=0):
    """hashStruct(SafeTx): ERC-8213's Message Hash, what a Ledger or Trezor shows beside the Domain
    Hash when it signs a Safe transaction."""
    # data: bytes or a 0x hex string. operation: CALL (0) or DELEGATECALL (1).
    if isinstance(data, str):
        data = _hex(data)
    if operation not in (CALL, DELEGATECALL):
        raise ValueError("operation must be 0 or 1")
    return keccak256(SAFE_TX_TYPEHASH + _addr(to) + _u256(value) + keccak256(data) + _u256(operation)
                     + _u256(safe_tx_gas) + _u256(base_gas) + _u256(gas_price) + _addr(gas_token)
                     + _addr(refund_receiver) + _u256(nonce))


def safe_tx_hash(chain_id, safe, to, value, data, operation, safe_tx_gas=0, base_gas=0, gas_price=0,
                 gas_token=ZERO, refund_receiver=ZERO, nonce=0):
    """The EIP-712 digest (ERC-8213's name; Safe calls it the safeTxHash)."""
    struct = message_hash(to, value, data, operation, safe_tx_gas, base_gas, gas_price, gas_token, refund_receiver, nonce)
    return keccak256(b"\x19\x01" + domain_separator(chain_id, safe) + struct)


def _fields(t):
    return (t["to"], t["value"], t.get("data") or "0x", t["operation"], t["safeTxGas"], t["baseGas"], t["gasPrice"],
            t.get("gasToken") or ZERO, t.get("refundReceiver") or ZERO, t["nonce"])


def from_service(chain_id, t):
    # One entry of the transaction service's multisig-transactions list, as parsed JSON.
    return safe_tx_hash(chain_id, t["safe"], *_fields(t))


def parts(chain_id, t):
    """(domain hash, message hash, EIP-712 digest) of a service entry: the three ERC-8213 values."""
    dom = domain_separator(chain_id, t["safe"])
    msg = message_hash(*_fields(t))
    return dom, msg, keccak256(b"\x19\x01" + dom + msg)


def verify_code(h):
    # The last 8 hex characters of the hash, lowercase as the Safe app shows them, for a phone call.
    return "".join("%02x" % b for b in h[-4:])
