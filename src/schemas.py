from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Abstract(BaseModel):
    language_code: str = "eng"
    content: str = ""


class KeywordSet(BaseModel):
    language_code: str = "eng"
    keywords: list[str] = Field(default_factory=list)


class Author(BaseModel):
    object_id: Optional[str] = None
    name: str = ""
    last_name: str = ""
    uuid: Optional[str] = None
    orcid_id: Optional[str] = None
    document_hash: Optional[str] = None

    @property
    def full_name(self) -> str:
        return f"{self.name} {self.last_name}".strip()

    @property
    def author_key(self) -> str:
        if self.orcid_id:
            return f"orcid:{self.orcid_id}"
        if self.uuid:
            return f"uuid:{self.uuid}"
        if self.object_id:
            return f"oid:{self.object_id}"
        return f"name:{self.last_name.lower()}|{self.name.lower()}"


class Publication(BaseModel):
    object_id: str
    title: str
    year: Optional[int] = None
    doi: Optional[str] = None
    abstracts: list[Abstract] = Field(default_factory=list)
    keywords: list[KeywordSet] = Field(default_factory=list)
    authors: list[Author] = Field(default_factory=list)
    topic_id: Optional[int] = None
    topic_label: Optional[str] = None

    def primary_abstract(self, prefer: str = "eng") -> str:
        if not self.abstracts:
            return ""
        for abs_ in self.abstracts:
            if abs_.language_code == prefer and abs_.content.strip():
                return abs_.content.strip()
        for abs_ in self.abstracts:
            if abs_.content.strip():
                return abs_.content.strip()
        return ""

    def keyword_list(self, prefer: str = "eng") -> list[str]:
        for ks in self.keywords:
            if ks.language_code == prefer and ks.keywords:
                return list(ks.keywords)
        for ks in self.keywords:
            if ks.keywords:
                return list(ks.keywords)
        return []

    def searchable_text(self) -> str:
        kws = " ".join(self.keyword_list())
        parts = [self.title or "", self.primary_abstract(), kws]
        return "\n\n".join(p for p in parts if p).strip()
