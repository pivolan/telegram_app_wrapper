# Stateless Telegram API Wrapper

⚠️ **Important Notice**: This REST API is available at `telegramrest.ru`. While you're welcome to use it, please be cautious and create a new Telegram account with a separate phone number for testing purposes. Do not use your personal Telegram account for testing to avoid any potential security risks.

To get started, you'll need to register your application:
1. Visit https://my.telegram.org/apps
2. Create a new application to obtain your `api_id` and `api_hash`

A lightweight, stateless HTTP wrapper around Telegram's API that allows you to interact with Telegram programmatically without maintaining persistent sessions. This API server provides a RESTful interface to manage your Telegram account, messages, and group interactions.

## Features

- 🔐 **Stateless Authentication**: No need to store session files - authentication state is maintained through session strings in headers
- 📱 **Account Management**: Login with phone number and manage 2FA
- 💬 **Message Operations**:
  - Send text messages and files
  - Delete messages
  - Forward messages between chats
  - Edit messages
  - Retrieve message history with filtering
  - Download media content
- 👥 **Group Management**:
  - Join public and private groups
  - Join via invite links
  - List all chats and groups
- 🔄 **Session Management**: Secure session handling with encrypted credentials

## Prerequisites

- Python 3.7+
- FastAPI
- Telethon
- Your Telegram API credentials (api_id and api_hash)

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/telegram-api-wrapper

# Install dependencies
pip install fastapi telethon uvicorn python-multipart aiofiles
```

## Configuration

Before starting the server, you need to obtain your Telegram API credentials:

1. Go to https://my.telegram.org/auth
2. Log in with your phone number
3. Go to 'API development tools'
4. Create a new application to get your `api_id` and `api_hash`

## Usage

### Starting the Server

```bash
uvicorn telegram_api_server_stateless:app --host 0.0.0.0 --port 8000
```

### Authentication Flow

1. **Initial Authentication**:
```http
POST http://localhost:8000/auth/send_code
Content-Type: application/json

{
  "phone": "+1234567890",
  "api_id": your_api_id,
  "api_hash": "your_api_hash"
}
```

2. **Verify Code**:
```http
POST http://localhost:8000/auth/verify_code
X-Session-String: {session_string_from_previous_response}
Content-Type: application/json

{
  "code": "12345"
}
```

3. **2FA (if enabled)**:
```http
POST http://localhost:8000/auth/verify_password
X-Session-String: {session_string}
Content-Type: application/json

{
  "password": "your_2fa_password"
}
```

### Basic Operations

#### Send Message
```http
POST http://localhost:8000/messages/send
X-Session-String: {session_string}
Content-Type: application/json

{
  "chat_id": "@username_or_chat_id",
  "text": "Hello, World!"
}
```

#### Get Messages
```http
GET http://localhost:8000/messages/?chat_id=123456&limit=100
X-Session-String: {session_string}
```

#### Join Group
```http
POST http://localhost:8000/groups/join
X-Session-String: {session_string}
Content-Type: application/json

{
  "group_identifier": "@group_username"
}
```

## Security Considerations

- The server encrypts API credentials in session strings
- No persistent storage of credentials or session data
- Each request requires authentication via session string
- Session strings should be treated as sensitive data

## Error Handling

The API returns appropriate HTTP status codes and error messages:

- `400`: Bad Request (invalid parameters)
- `401`: Unauthorized (invalid session)
- `403`: Forbidden (insufficient permissions)
- `404`: Not Found (chat/message not found)
- `429`: Too Many Requests (Telegram rate limit)

## Use Cases

This wrapper is particularly useful for:

- Building chat bots without session management
- Automating Telegram operations
- Integration with other services
- Managing multiple Telegram accounts
- Creating custom Telegram clients

## Limitations

- Rate limits apply as per Telegram's API restrictions
- Some Telegram features might not be available
- Media operations are temporary (files are deleted after sending)

## Contributing

Contributions are welcome! Please feel free to submit pull requests or create issues for bugs and feature requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This project is not officially affiliated with Telegram. Use responsibly and in accordance with Telegram's terms of service.