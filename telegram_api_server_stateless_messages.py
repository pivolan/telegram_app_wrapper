from typing import Optional, List
from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form
from pydantic import BaseModel
import aiofiles
import os
import mimetypes
from datetime import datetime
from telethon.errors import (
    MessageIdInvalidError,
    MessageDeleteForbiddenError,
    MessageEmptyError,
    MessageTooLongError,
    MessageAuthorRequiredError,
    MessageNotModifiedError
)
from telethon.tl.types import InputMediaUploadedDocument, DocumentAttributeFilename
from telegram_api_server_stateless_utils import get_client_from_session

router = APIRouter(prefix="/messages", tags=["messages"])

class SendMessageRequest(BaseModel):
    chat_id: str
    text: str
    reply_to_message_id: Optional[int] = None

class ForwardMessageRequest(BaseModel):
    from_chat_id: str
    to_chat_id: str
    message_id: int

class EditMessageRequest(BaseModel):
    chat_id: str
    message_id: str
    new_text: str

class SendMessageResponse(BaseModel):
    success: bool
    message_id: int
    date: datetime

class DeleteMessageRequest(BaseModel):
    chat_id: str
    message_ids: List[int]

class DeleteMessageResponse(BaseModel):
    success: bool
    deleted_messages: List[int]

# Создаем временную директорию для загрузки файлов
UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/send", response_model=SendMessageResponse)
async def send_message(
        message: SendMessageRequest,
        session_string: str = Header(..., alias="X-Session-String")
):
    """Send text message to chat/group"""
    try:
        client = await get_client_from_session(session_string)

        entity = await client.get_input_entity(message.chat_id)
        sent_message = await client.send_message(
            entity=entity,
            message=message.text,
            reply_to=message.reply_to_message_id
        )

        return SendMessageResponse(
            success=True,
            message_id=sent_message.id,
            date=sent_message.date
        )
    except MessageEmptyError:
        raise HTTPException(status_code=400, detail="Message text cannot be empty")
    except MessageTooLongError:
        raise HTTPException(status_code=400, detail="Message text is too long")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/send_with_file", response_model=SendMessageResponse)
async def send_message_with_file(
        chat_id: str = Form(...),
        text: Optional[str] = Form(None),
        reply_to_message_id: Optional[int] = Form(None),
        file: UploadFile = File(...),
        session_string: str = Header(..., alias="X-Session-String")
):
    """Send message with file attachment"""
    try:
        client = await get_client_from_session(session_string)

        # Сохраняем файл временно
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        try:
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)

            # Определяем MIME-тип файла по расширению
            mime_type, _ = mimetypes.guess_type(file.filename)
            if mime_type is None:
                mime_type = 'application/octet-stream'  # дефолтный тип если не удалось определить

            # Отправляем файл
            entity = await client.get_input_entity(chat_id)
            sent_message = await client.send_file(
                entity=entity,
                file=file_path,
                caption=text,
                reply_to=reply_to_message_id,
                attributes=[DocumentAttributeFilename(file_name=file.filename)]
            )

            return SendMessageResponse(
                success=True,
                message_id=sent_message.id,
                date=sent_message.date
            )

        finally:
            # Удаляем временный файл
            if os.path.exists(file_path):
                os.remove(file_path)

    except MessageEmptyError:
        raise HTTPException(status_code=400, detail="Message caption cannot be empty")
    except MessageTooLongError:
        raise HTTPException(status_code=400, detail="Message caption is too long")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/delete", response_model=DeleteMessageResponse)
async def delete_messages(
        delete_request: DeleteMessageRequest,
        session_string: str = Header(..., alias="X-Session-String")
):
    """Delete one or multiple messages"""
    try:
        client = await get_client_from_session(session_string)

        entity = await client.get_input_entity(delete_request.chat_id)

        # Пытаемся удалить сообщения
        deleted_messages = []
        for message_id in delete_request.message_ids:
            try:
                await client.delete_messages(entity, message_id)
                deleted_messages.append(message_id)
            except MessageIdInvalidError:
                continue  # Пропускаем некорректные ID сообщений
            except MessageDeleteForbiddenError:
                continue  # Пропускаем сообщения, которые нельзя удалить
            except MessageAuthorRequiredError:
                continue  # Пропускаем сообщения, для удаления которых нужны права автора

        if not deleted_messages:
            raise HTTPException(
                status_code=400,
                detail="None of the specified messages could be deleted"
            )

        return DeleteMessageResponse(
            success=True,
            deleted_messages=deleted_messages
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/forward", response_model=SendMessageResponse)
async def forward_message(
        forward_request: ForwardMessageRequest,
        session_string: str = Header(..., alias="X-Session-String")
):
    """Forward message from one chat to another"""
    try:
        client = await get_client_from_session(session_string)

        # Получаем исходный и целевой чаты
        from_entity = await client.get_input_entity(forward_request.from_chat_id)
        to_entity = await client.get_input_entity(forward_request.to_chat_id)

        # Пересылаем сообщение
        forwarded_message = await client.forward_messages(
            entity=to_entity,
            messages=forward_request.message_id,
            from_peer=from_entity
        )

        return SendMessageResponse(
            success=True,
            message_id=forwarded_message.id,
            date=forwarded_message.date
        )

    except MessageIdInvalidError:
        raise HTTPException(status_code=400, detail="Invalid message ID")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/edit", response_model=SendMessageResponse)
async def edit_message(
        edit_request: EditMessageRequest,
        session_string: str = Header(..., alias="X-Session-String")
):
    """Edit existing message"""
    try:
        client = await get_client_from_session(session_string)

        entity = await client.get_input_entity(edit_request.chat_id)

        # Редактируем сообщение
        edited_message = await client.edit_message(
            entity=entity,
            message=edit_request.message_id,
            text=edit_request.new_text
        )

        return SendMessageResponse(
            success=True,
            message_id=edited_message.id,
            date=edited_message.date
        )

    except MessageIdInvalidError:
        raise HTTPException(status_code=400, detail="Invalid message ID")
    except MessageNotModifiedError:
        raise HTTPException(status_code=400, detail="Message content is not modified")
    except MessageEmptyError:
        raise HTTPException(status_code=400, detail="New message text cannot be empty")
    except MessageTooLongError:
        raise HTTPException(status_code=400, detail="New message text is too long")
    except MessageAuthorRequiredError:
        raise HTTPException(status_code=403, detail="You must be the author of the message to edit it")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))