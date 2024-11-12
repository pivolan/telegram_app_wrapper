import asyncio
import os
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.sessions import StringSession
from telethon.tl.types import Channel, Chat, User, InputPeerChannel, InputPeerChat

# В начале файла, где остальные импорты:
from telegram_api_server_stateless_groups import router as groups_router
from telegram_api_server_stateless_messages import router as messages_router
from telegram_api_server_stateless_utils import (
    get_client_from_session,
    encode_session_with_credentials,
    clients,
    decode_session_with_credentials
)

# После создания приложения (после строки app = FastAPI()):
app = FastAPI()
app.include_router(groups_router)
app.include_router(messages_router)


class ApiCredentials(BaseModel):
    phone: str
    api_id: int
    api_hash: str


class VerificationCode(BaseModel):
    code: str


class Password(BaseModel):
    password: str


class AuthResponse(BaseModel):
    message: str
    next_step: str
    session_string: Optional[str] = None


class ChatInfo(BaseModel):
    name: str
    id: int
    type: str
    members_count: Optional[int] = None
    is_private: bool
    username: Optional[str] = None


class ChatsResponse(BaseModel):
    chats: List[ChatInfo]
    total_count: int


@app.post("/auth/send_code", response_model=AuthResponse)
async def send_code(credentials: ApiCredentials):
    try:
        # Create new client with provided credentials
        client = TelegramClient(StringSession(), credentials.api_id, credentials.api_hash)
        await client.connect()

        # Send authentication code
        await client.send_code_request(credentials.phone)

        # Get session and combine with encrypted credentials
        temp_session = client.session.save()
        combined_session = encode_session_with_credentials(
            temp_session,
            credentials.api_id,
            credentials.api_hash
        )

        # Store client
        clients[combined_session] = client

        return AuthResponse(
            message="Verification code sent",
            next_step="verify_code",
            session_string=combined_session
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/auth/verify_code", response_model=AuthResponse)
async def verify_code(
        verification_data: VerificationCode,
        session_string: str = Header(..., alias="X-Session-String")
):
    try:
        if session_string not in clients:
            raise HTTPException(status_code=401, detail="Invalid session")

        client = clients[session_string]
        session, api_id, api_hash = decode_session_with_credentials(session_string)

        try:
            # Try to sign in with the code
            await client.sign_in(code=verification_data.code)

            # Get new session and combine with credentials
            new_session = client.session.save()
            new_combined_session = encode_session_with_credentials(
                new_session,
                api_id,
                api_hash
            )

            # Update clients dictionary
            clients[new_combined_session] = client
            del clients[session_string]

            return AuthResponse(
                message="Successfully authenticated",
                next_step="completed",
                session_string=new_combined_session
            )
        except Exception as e:
            if "password" in str(e).lower():
                return AuthResponse(
                    message="2FA password required",
                    next_step="verify_password",
                    session_string=session_string
                )
            raise e

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/auth/verify_password", response_model=AuthResponse)
async def verify_password(
        password_data: Password,
        session_string: str = Header(..., alias="X-Session-String")
):
    try:
        if session_string not in clients:
            raise HTTPException(status_code=401, detail="Invalid session")

        client = clients[session_string]
        session, api_id, api_hash = decode_session_with_credentials(session_string)

        # Sign in with password
        await client.sign_in(password=password_data.password)

        # Get new session and combine with credentials
        new_session = client.session.save()
        new_combined_session = encode_session_with_credentials(
            new_session,
            api_id,
            api_hash
        )

        # Update clients dictionary
        clients[new_combined_session] = client
        del clients[session_string]

        return AuthResponse(
            message="Successfully authenticated with 2FA",
            next_step="completed",
            session_string=new_combined_session
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/chats", response_model=ChatsResponse)
async def get_chats(
        limit: int = 100,
        session_string: str = Header(..., alias="X-Session-String")
):
    try:
        client = await get_client_from_session(session_string)

        # Get dialogs
        dialogs = await client.get_dialogs(limit=limit)

        chats_list = []
        for dialog in dialogs:
            entity = dialog.entity

            # Determine chat type
            if isinstance(entity, Channel):
                chat_type = "channel" if entity.broadcast else "supergroup"
            elif isinstance(entity, Chat):
                chat_type = "group"
            elif isinstance(entity, User):
                chat_type = "private"
            else:
                continue

            chat_info = ChatInfo(
                name=dialog.name,
                id=dialog.id,
                type=chat_type,
                members_count=getattr(entity, 'participants_count', None),
                is_private=not hasattr(entity, 'username') or entity.username is None,
                username=getattr(entity, 'username', None)
            )

            chats_list.append(chat_info)

        return ChatsResponse(
            chats=chats_list,
            total_count=len(chats_list)
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/auth/logout")
async def logout(session_string: str = Header(..., alias="X-Session-String")):
    try:
        if session_string in clients:
            client = clients[session_string]
            await client.log_out()
            await client.disconnect()
            del clients[session_string]

        return {"message": "Successfully logged out"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.on_event("shutdown")
async def shutdown_event():
    # Disconnect all active clients when server stops
    for client in clients.values():
        try:
            await client.disconnect()
        except Exception:
            pass


class MessageInfo(BaseModel):
    id: int
    text: Optional[str]
    date: datetime
    sender_id: Optional[int]
    sender_username: Optional[str]
    sender_name: Optional[str]
    reply_to_msg_id: Optional[int] = None
    forward_from: Optional[str] = None
    media_type: Optional[str] = None
    is_pinned: Optional[bool] = False


class MessagesResponse(BaseModel):
    messages: List[MessageInfo]
    total_count: int
    has_more: bool
    next_offset: Optional[int]


@app.get("/messages/media/{message_id}")
async def get_media_content(
        message_id: int,
        chat_id: str,
        session_string: str = Header(..., alias="X-Session-String")
):
    try:
        client = await get_client_from_session(session_string)

        if not await client.is_user_authorized():
            raise HTTPException(status_code=401, detail="Authentication required")

        try:
            # Преобразуем chat_id в число, если это возможно
            numeric_id = int(chat_id)

            # Определяем тип чата по ID
            if numeric_id < 0:
                # Для супергрупп и каналов ID начинается с -100
                if str(numeric_id).startswith('-100'):
                    # Убираем -100 из ID
                    channel_id = int(str(abs(numeric_id))[3:])
                    entity = InputPeerChannel(channel_id=channel_id, access_hash=0)
                else:
                    # Для обычных групп просто используем ID
                    entity = InputPeerChat(chat_id=abs(numeric_id))
            else:
                # Для пользователей и других типов пытаемся получить напрямую
                entity = await client.get_input_entity(numeric_id)
        except ValueError:
            # Если не получилось преобразовать в число или найти по ID,
            # пробуем получить по username
            try:
                entity = await client.get_input_entity(chat_id)
            except ValueError as e:
                raise HTTPException(status_code=404, detail=f"Chat not found: {str(e)}")

        # Получаем сообщение
        message = await client.get_messages(entity, ids=message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        if not message.media:
            raise HTTPException(status_code=400, detail="Message has no media content")

        # Создаем временную директорию, если её нет
        os.makedirs("temp_downloads", exist_ok=True)

        # Скачиваем файл
        path = await message.download_media(file="temp_downloads/")

        if not path:
            raise HTTPException(status_code=400, detail="Failed to download media")

        # Определяем тип контента
        content_type = "application/octet-stream"
        filename = os.path.basename(path)

        if message.photo:
            content_type = "image/jpeg"
            if not filename.endswith('.jpg'):
                filename += '.jpg'
        elif message.video:
            content_type = "video/mp4"
            if not filename.endswith('.mp4'):
                filename += '.mp4'
        elif message.document:
            if message.document.mime_type:
                content_type = message.document.mime_type
            if message.file and message.file.name:
                filename = message.file.name

        # Возвращаем файл и удаляем его после отправки
        return FileResponse(
            path=path,
            media_type=content_type,
            filename=filename,
            background=asyncio.create_task(cleanup_file(path))
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


async def cleanup_file(path: str):
    """Удаляет временный файл после отправки"""
    await asyncio.sleep(1)  # Даем время на отправку файла
    try:
        os.remove(path)
    except:

        pass


@app.get("/messages/", response_model=MessagesResponse)
async def get_messages(
        chat_id: str,
        limit: int = 100,
        offset_id: int = 0,
        search: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        session_string: str = Header(..., alias="X-Session-String")
):
    try:
        client = await get_client_from_session(session_string)

        if not await client.is_user_authorized():
            raise HTTPException(status_code=401, detail="Authentication required")

        try:
            # Преобразуем chat_id в число, если это возможно
            numeric_id = int(chat_id)

            # Определяем тип чата по ID
            if numeric_id < 0:
                # Для супергрупп и каналов ID начинается с -100
                if str(numeric_id).startswith('-100'):
                    # Убираем -100 из ID
                    channel_id = int(str(abs(numeric_id))[3:])
                    entity = InputPeerChannel(channel_id=channel_id, access_hash=0)
                else:
                    # Для обычных групп просто используем ID
                    entity = InputPeerChat(chat_id=abs(numeric_id))
            else:
                # Для пользователей и других типов пытаемся получить напрямую
                entity = await client.get_input_entity(numeric_id)
        except ValueError:
            # Если не получилось преобразовать в число или найти по ID,
            # пробуем получить по username
            try:
                entity = await client.get_input_entity(chat_id)
            except ValueError as e:
                raise HTTPException(status_code=404, detail=f"Chat not found: {str(e)}")

        try:
            # Добавляем задержку перед запросом сообщений
            await asyncio.sleep(2)

            # Формируем параметры запроса
            kwargs = {
                "limit": limit,
                "offset_id": offset_id,
                "reverse": False
            }

            if search:
                kwargs["search"] = search

            if from_date:
                kwargs["min_date"] = from_date
            if to_date:
                kwargs["max_date"] = to_date

            messages = await client.get_messages(entity, **kwargs)

            messages_list = []
            for msg in messages:
                media_type = None
                if msg.photo:
                    media_type = "photo"
                elif msg.video:
                    media_type = "video"
                elif msg.document:
                    media_type = "document"
                elif msg.voice:
                    media_type = "voice"
                elif msg.audio:
                    media_type = "audio"

                sender_id = None
                sender_username = None
                sender_name = None

                if msg.sender:
                    sender_id = msg.sender.id
                    sender_username = getattr(msg.sender, 'username', None)
                    sender_name = msg.sender.first_name
                    if hasattr(msg.sender, 'last_name') and msg.sender.last_name:
                        sender_name += f" {msg.sender.last_name}"

                forward_from = None
                if msg.forward:
                    if msg.forward.from_name:
                        forward_from = msg.forward.from_name
                    elif msg.forward.sender:
                        forward_from = getattr(msg.forward.sender, 'username', None) or \
                                       msg.forward.sender.first_name

                message_info = MessageInfo(
                    id=msg.id,
                    text=msg.text if msg.text else None,
                    date=msg.date,
                    sender_id=sender_id,
                    sender_username=sender_username,
                    sender_name=sender_name,
                    reply_to_msg_id=msg.reply_to_msg_id,
                    forward_from=forward_from,
                    media_type=media_type,
                    is_pinned=msg.pinned
                )
                messages_list.append(message_info)

                if len(messages_list) % 20 == 0:
                    await asyncio.sleep(1)

            has_more = len(messages) == limit
            next_offset = messages[-1].id if has_more and messages else None

            return MessagesResponse(
                messages=messages_list,
                total_count=len(messages_list),
                has_more=has_more,
                next_offset=next_offset
            )

        except FloodWaitError as e:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Too many requests",
                    "wait_seconds": e.seconds,
                    "message": f"Please wait {e.seconds} seconds before making another request"
                }
            )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))