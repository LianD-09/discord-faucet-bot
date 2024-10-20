from base64 import b64decode
from ecdsa import SECP256k1, VerifyingKey
from web3 import Web3
from eth_utils import to_checksum_address
from hashlib import sha256
from bech32 import bech32_encode, convertbits
from Crypto.Hash import RIPEMD160

def decompress_pubkey(pubkey_bytes):
    if len(pubkey_bytes) != 33:
        raise ValueError("Public key is not compressed or has invalid length")
    vk = VerifyingKey.from_string(pubkey_bytes, curve=SECP256k1)
    return vk.pubkey.point.to_bytes()

def uncompressed_pub_key_to_evm(public_key):
    keccak_hash = Web3().keccak(public_key)
    return to_checksum_address('0x' + keccak_hash[-20:].hex())

def pubkey_to_bech32(pubkey_bytes, bech32_prefix):
        pubkey_bytes = b64decode(pubkey_bytes)
        sha256_digest = sha256(pubkey_bytes).digest()
        ripemd160 = RIPEMD160.new()
        ripemd160.update(sha256_digest)
        ripemd160_digest = ripemd160.digest()
        converted_bits = convertbits(ripemd160_digest, 8, 5)
        return bech32_encode(bech32_prefix, converted_bits)

def base64_to_hex(base64_str):
    pubkey_bytes = b64decode(base64_str)
    return pubkey_bytes.hex().upper()

def export_pub_key(pub_key):
    
    compressed_pubkey_bytes = b64decode(pub_key)
    uncompressed_pubkey_bytes = decompress_pubkey(compressed_pubkey_bytes)
    ethereum_address = uncompressed_pub_key_to_evm(uncompressed_pubkey_bytes)
    cosmos_address = pubkey_to_bech32(pub_key, 'story')
    valoper = pubkey_to_bech32(pub_key, 'storyvaloper')
    valcons = pubkey_to_bech32(pub_key, 'storyvalcons')
    consensus_hex = base64_to_hex(pub_key)
    
    msg =  "```\n" \
           "-------------------------------------------------------------\n" \
          f"Your compressed 33-byte secp256k1 public key (base64-encoded): {pub_key}\n" \
          f"Ethereum Address: {ethereum_address}\n" \
          f"Compressed Public Key (hex): {compressed_pubkey_bytes.hex()}\n" \
          f"Uncompressed Public Key (hex): {uncompressed_pubkey_bytes.hex()}\n" \
          "-------------------------------------------------------------\n" \
          f"Cosmos Wallet Address (bech32): {cosmos_address}\n" \
          f"Valoper Address (bech32): {valoper}\n" \
          f"Valcons Address (bech32): {valcons}\n" \
          f"Consensus HEX Address (hex): {consensus_hex}\n" \
          "-------------------------------------------------------------\n" \
          "```"
    return msg

"""
-------------------------------------------------------------
Your compressed 33-byte secp256k1 public key (base64-encoded): A3mhZISLH2SDSWmbzxNlBkHSynKZ7yh1ugPD1g0lgO5m
Ethereum Address: 0x7F96aea27dfF22dc8A8b3691B1e553e7864e3E8A
Compressed Public Key (hex): 0379a164848b1f648349699bcf13650641d2ca7299ef2875ba03c3d60d2580ee66
Uncompressed Public Key (hex): 79a164848b1f648349699bcf13650641d2ca7299ef2875ba03c3d60d2580ee669b32f80e3f36b087925ece0fd150c84f434ebd49d1f1c53bf6631708f02ab4ef
-------------------------------------------------------------
Cosmos Wallet Address (bech32): story1qzgsp7x8pgwm8gw42kq2w8v2tyn6egjcnufp2v
Valoper Address (bech32): storyvaloper1qzgsp7x8pgwm8gw42kq2w8v2tyn6egjcanaqp8
Valcons Address (bech32): storyvalcons1qzgsp7x8pgwm8gw42kq2w8v2tyn6egjcfqwudx
Consensus HEX Address (hex): 0379A164848B1F648349699BCF13650641D2CA7299EF2875BA03C3D60D2580EE66
-------------------------------------------------------------
"""
# pip install ecdsa web3 eth_utils bech32 pycryptodome