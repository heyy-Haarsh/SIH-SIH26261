from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Document, DocumentVersion, ExtractedField
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository):
    def get_by_requirement(self, application_id: str, requirement_code: str) -> Optional[Document]:
        stmt = (
            select(Document)
            .where(Document.application_id == application_id, Document.requirement_code == requirement_code)
            .options(selectinload(Document.versions))
        )
        return self.db.scalars(stmt).first()

    def list_for_application(self, application_id: str) -> list[Document]:
        stmt = (
            select(Document)
            .where(Document.application_id == application_id)
            .options(selectinload(Document.versions).selectinload(DocumentVersion.extracted_fields))
            .order_by(Document.created_at)
        )
        return list(self.db.scalars(stmt))

    def add_version(self, version: DocumentVersion) -> DocumentVersion:
        self.db.add(version)
        return version

    def add_fields(self, fields: list[ExtractedField]) -> None:
        self.db.add_all(fields)
