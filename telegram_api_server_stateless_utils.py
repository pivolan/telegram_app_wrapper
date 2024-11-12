import base64
import struct
from typing import Optional
from fastapi import HTTPException
from telethon import TelegramClient
from telethon.sessions import StringSession

# Dictionary to store active clients
clients = {}

async def get_client_from_session(session_string: str) -> TelegramClient:
    """Create or get client from session string with credentials"""
    if session_string in clients:
        return clients[session_string]

    try:
        # Extract session and credentials
        session, api_id, api_hash = decode_session_with_credentials(session_string)

        # Create client with extracted credentials
        client = TelegramClient(StringSession(session), api_id, api_hash)
        await client.connect()

        if not await client.is_user_authorized():
            raise HTTPException(status_code=401, detail="Invalid session")

        clients[session_string] = client
        return client
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid session")

def encode_session_with_credentials(session: str, api_id: int, api_hash: str) -> str:
    """Combine session string with encrypted credentials"""
    encrypted_creds = encrypt_credentials(api_id, api_hash)
    return f"{session}:{encrypted_creds}"

def decode_session_with_credentials(combined_session: str) -> tuple[str, int, str]:
    """Extract session string and credentials"""
    try:
        session, encrypted_creds = combined_session.split(':', 1)
        api_id, api_hash = decrypt_credentials(encrypted_creds)
        return session, api_id, api_hash
    except ValueError as e:
        raise HTTPException(status_code=401, detail="Invalid session format")

# Your encryption functions
ENCRYPT_KEY = base64.b64decode('v1KvK4AGqhWQUm9L87Dh7PzPKl2EQeQA3J0H2InPMUo=')


def encrypt_credentials(api_id: int, api_hash: str) -> str:
    """Encrypt API credentials and return as base64 string"""
    # Convert api_id to bytes (8 bytes for int64)
    api_id_bytes = struct.pack('!Q', api_id)

    # Get bytes of api_hash
    api_hash_bytes = api_hash.encode('utf-8')

    # Combine the bytes with length prefix for api_hash
    combined = api_id_bytes + len(api_hash_bytes).to_bytes(1, 'big') + api_hash_bytes

    # XOR with key (cycling if necessary)
    encrypted = bytes(b ^ ENCRYPT_KEY[i % len(ENCRYPT_KEY)]
                      for i, b in enumerate(combined))

    return base64.urlsafe_b64encode(encrypted).decode('ascii')


def decrypt_credentials(encrypted_str: str) -> tuple[int, str]:
    """Decrypt base64 string back to API credentials"""
    try:
        # Decode base64
        encrypted = base64.urlsafe_b64decode(encrypted_str.encode('ascii'))

        # XOR with key (cycling if necessary)
        decrypted = bytes(b ^ ENCRYPT_KEY[i % len(ENCRYPT_KEY)]
                          for i, b in enumerate(encrypted))

        # Extract api_id (first 8 bytes)
        api_id = struct.unpack('!Q', decrypted[:8])[0]

        # Extract api_hash length and then api_hash
        api_hash_len = decrypted[8]
        api_hash = decrypted[9:9 + api_hash_len].decode('utf-8')

        return api_id, api_hash
    except Exception as e:
        raise ValueError("Failed to decrypt credentials") from e
