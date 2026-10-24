from dataclasses import dataclass, field
from uuid import UUID

from app.retrieval.models import SourcePassage
from app.retrieval.retriever import DocumentRetriever


@dataclass
class DocumentAgentDeps:
    user_id: UUID
    thread_id: UUID
    retriever: DocumentRetriever
    # Every passage a tool returned this turn; the only chunks the answer may cite.
    retrieved: dict[UUID, SourcePassage] = field(default_factory=dict)
