from __future__ import annotations

from pydantic import BaseModel


# ---- Drive API response models ----

class FileListItem(BaseModel):
    file_token: str
    file_name: str
    type: str  # "folder" or "file"
    size: int = 0
    last_modified_time: str = ""


class DriveFileListResponse(BaseModel):
    items: list[FileListItem]
    has_more: bool
    page_token: str | None = None


class DriveCreateResponse(BaseModel):
    file_token: str
    file_name: str
    type: str


# ---- Card interaction models ----

class CardActionValue(BaseModel):
    action: str
    folder_token: str | None = None
    file_token: str | None = None
    file_name: str | None = None
    parent_token: str | None = None
    page_token: str | None = None


# ---- Event data models ----

class MessageEvent(BaseModel):
    message_id: str
    chat_id: str
    sender_id: str
    message_type: str
    content: str  # parsed text content


class CardCallbackEvent(BaseModel):
    token: str
    card_id: str
    user_id: str
    open_id: str | None = None
    union_id: str | None = None
    chat_id: str | None = None
    action: CardActionValue  # parsed from card callback value
