from typing import Optional
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors import (
    ChannelPrivateError,
    InviteHashEmptyError,
    InviteHashExpiredError,
    InviteHashInvalidError,
    UserAlreadyParticipantError
)

from telegram_api_server_stateless_utils import get_client_from_session  # импортируем функцию из основного файла

router = APIRouter(prefix="/groups", tags=["groups"])
from typing import Optional
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from telethon.tl.functions.channels import JoinChannelRequest, GetFullChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest, GetFullChatRequest
from telethon.tl.types import Channel, Chat
from telethon.errors import (
    ChannelPrivateError,
    InviteHashEmptyError,
    InviteHashExpiredError,
    InviteHashInvalidError,
    UserAlreadyParticipantError
)

class JoinGroupRequest(BaseModel):
    group_identifier: str

class JoinResponse(BaseModel):
    success: bool
    message: str
    id: Optional[int] = None
    title: Optional[str] = None
    username: Optional[str] = None
    description: Optional[str] = None
    photo_url: Optional[str] = None

@router.post("/join", response_model=JoinResponse)
async def join_group(
        join_request: JoinGroupRequest,
        session_string: str = Header(..., alias="X-Session-String")
):
    try:
        client = await get_client_from_session(session_string)

        group_identifier = join_request.group_identifier.strip()
        entity = None

        # Определяем тип идентификатора группы и присоединяемся
        if group_identifier.startswith(('https://t.me/', 't.me/')):
            # Убираем протокол и домен
            parts = group_identifier.split('/')
            if len(parts) > 1:
                last_part = parts[-1]
                # Убираем @ если он есть в URL
                if last_part.startswith('@'):
                    last_part = last_part[1:]

                if 'joinchat' in parts:
                    invite_hash = last_part
                elif last_part.startswith('+'):
                    invite_hash = last_part[1:]
                else:
                    group_identifier = last_part
                    invite_hash = None

                if invite_hash:
                    try:
                        result = await client(ImportChatInviteRequest(invite_hash))
                        entity = result.chats[0]
                    except UserAlreadyParticipantError:
                        # Если уже участник, получаем информацию о группе
                        entity = await client.get_entity(group_identifier)
                else:
                    # Для публичной группы
                    try:
                        entity = await client.get_entity(group_identifier)
                        result = await client(JoinChannelRequest(entity))
                        entity = result.chats[0] if result else entity
                    except ValueError:
                        # Если не удалось найти по юзернейму, пробуем с @
                        try:
                            entity = await client.get_entity(f"@{group_identifier}")
                            result = await client(JoinChannelRequest(entity))
                            entity = result.chats[0] if result else entity
                        except:
                            raise ValueError(f"Could not find group: {group_identifier}")

        elif group_identifier.startswith('+'):
            invite_hash = group_identifier[1:]
            try:
                result = await client(ImportChatInviteRequest(invite_hash))
                entity = result.chats[0]
            except UserAlreadyParticipantError:
                entity = await client.get_entity(group_identifier)
        else:
            # Убираем @ если он есть
            if group_identifier.startswith('@'):
                group_identifier = group_identifier[1:]

            try:
                entity = await client.get_entity(group_identifier)
                result = await client(JoinChannelRequest(entity))
                entity = result.chats[0] if result else entity
            except ValueError:
                # Если не удалось найти по юзернейму, пробуем с @
                try:
                    entity = await client.get_entity(f"@{group_identifier}")
                    result = await client(JoinChannelRequest(entity))
                    entity = result.chats[0] if result else entity
                except:
                    raise ValueError(f"Could not find group: {group_identifier}")

        if not entity:
            raise HTTPException(status_code=404, detail="Group/channel not found")

        # Получаем полную информацию о чате в зависимости от его типа
        try:
            if isinstance(entity, Channel):
                full_chat = await client(GetFullChannelRequest(channel=entity))
                description = full_chat.full_chat.about
            elif isinstance(entity, Chat):
                full_chat = await client(GetFullChatRequest(chat_id=entity.id))
                description = full_chat.about
            else:
                description = None
        except Exception:
            description = None

        # Формируем URL для фото, если оно есть
        photo_url = None
        if hasattr(entity, 'photo') and entity.photo:
            try:
                photo = await client.download_profile_photo(entity, file=bytes)
                if photo:
                    photo_url = f"/photos/{entity.id}.jpg"
            except Exception:
                pass

        return JoinResponse(
            success=True,
            message="Successfully joined",
            id=entity.id,
            title=entity.title,
            username=entity.username if hasattr(entity, 'username') else None,
            description=description,
            photo_url=photo_url
        )

    except InviteHashEmptyError:
        raise HTTPException(status_code=400, detail="Invalid invitation link - hash is empty")
    except InviteHashExpiredError:
        raise HTTPException(status_code=400, detail="This invitation link has expired")
    except InviteHashInvalidError:
        raise HTTPException(status_code=400, detail="Invalid invitation link")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))