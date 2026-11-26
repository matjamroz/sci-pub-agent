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

    def publication_search_text(self, max_chars: int = 3200) -> str:
        """Text that was embedded: title, every abstract, every keyword string.

        The Kaggle run stored one vector per publication and cut the text at
        3200 characters. Keep the same cut so the stored passage matches the vector.
        """
        parts: list[str] = []
        title = " ".join((self.title or "").split())
        if title:
            parts.append(title)
        for abstract in self.abstracts:
            content = " ".join(abstract.content.split())
            if content:
                parts.append(content)
        keywords: list[str] = []
        for group in self.keywords:
            for keyword in group.keywords:
                cleaned = " ".join(keyword.split())
                if cleaned:
                    keywords.append(cleaned)
        if keywords:
            parts.append(" ".join(keywords))
        text = "\n\n".join(parts)
        if max_chars and len(text) > max_chars:
            return text[:max_chars]
        return text

    def searchable_text(self) -> str:
        return self.publication_search_text(max_chars=0)
