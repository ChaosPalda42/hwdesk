from __future__ import annotations

import os
import uuid
from typing import Callable

from src.repositories.attachments import AttachmentRepository
from src.repositories.audit import AuditRepository
from src.config import ATTACHMENT_KINDS, ATTACHMENT_OWNERS, ATTACHMENT_ALLOWED_TYPES


class AttachmentError(ValueError):
    pass


class AttachmentService:
    def __init__(self, repo: AttachmentRepository, audit: AuditRepository, directory: str, max_bytes: int, owner_exists: Callable[[str, int], bool]):
        self.repo = repo
        self.audit = audit
        self.directory = directory
        self.max_bytes = max_bytes
        self.owner_exists = owner_exists

    def store(self, actor: str, owner_type: str, owner_id: int, kind: str, filename: str, mime_type: str, data: bytes) -> dict:
        # Validate owner type
        if owner_type not in ATTACHMENT_OWNERS:
            raise AttachmentError("Invalid owner type")
        
        # Validate that owner exists
        if not self.owner_exists(owner_type, owner_id):
            raise AttachmentError("Owner does not exist")
            
        # Validate kind
        if kind not in ATTACHMENT_KINDS:
            raise AttachmentError("Invalid attachment kind")
            
        # Validate mime type
        if mime_type not in ATTACHMENT_ALLOWED_TYPES:
            raise AttachmentError("Invalid MIME type")
            
        # Validate data size
        if len(data) > self.max_bytes or len(data) <= 0:
            raise AttachmentError("Data size exceeds limit or is empty")
            
        # Process filename
        filename = os.path.basename(filename).strip()
        if not filename:
            filename = "soubor"
            
        # Extract extension and make it lowercase
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        
        # Generate stored name
        stored_name = f"{owner_type}-{owner_id}-{uuid.uuid4().hex}{ext}"
        
        # Ensure directory exists
        os.makedirs(self.directory, exist_ok=True)
        
        # Write file to disk
        file_path = os.path.join(self.directory, stored_name)
        with open(file_path, "wb") as f:
            f.write(data)
            
        # Create attachment record in database
        attachment = self.repo.create(
            owner_type=owner_type,
            owner_id=owner_id,
            kind=kind,
            filename=filename,
            stored_name=stored_name,
            mime_type=mime_type,
            size=len(data),
            uploaded_by=actor
        )
        
        # Audit the action
        self.audit.record(
            actor=actor,
            action="attachment.added",
            entity=owner_type,
            entity_id=owner_id,
            details={"filename": filename, "kind": kind}
        )
        
        return attachment

    def path_for(self, attachment_id: int) -> str:
        attachment = self.repo.get(attachment_id)
        if not attachment:
            raise AttachmentError("Unknown attachment")
            
        return os.path.join(self.directory, attachment["stored_name"])

    def delete(self, actor: str, attachment_id: int) -> bool:
        attachment = self.repo.get(attachment_id)
        if not attachment:
            return False
            
        # Delete file from disk
        file_path = os.path.join(self.directory, attachment["stored_name"])
        try:
            os.remove(file_path)
        except OSError:
            # File might have been deleted already, which is fine
            pass
            
        # Delete record from database
        deleted = self.repo.delete(attachment_id)
        
        # Audit the action
        self.audit.record(
            actor=actor,
            action="attachment.deleted",
            entity=attachment["owner_type"],
            entity_id=attachment["owner_id"],
            details={"filename": attachment["filename"], "kind": attachment["kind"]}
        )
        
        return deleted