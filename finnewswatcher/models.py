from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal, List, Optional, Dict
from pydantic import BaseModel, HttpUrl, Field, field_validator


SourceType = Literal["rns", "filing", "press", "wire"]
EventClass = Literal["Earnings", "Guidance", "M&A", "Financing", "Exec", "Legal-Reg", "Product-Customer", "Macro"]


class NormalizedItem(BaseModel):

    """
    This is the single canonical schema for any fetched article/filing/press item that flows through fetch -> classify -> score -> summarize -> judge -> deliver.
    """

    # --- Source --- (REQUIRED)
    id: str
    published_at: datetime
    source_name: str
    source_type: SourceType
    url: HttpUrl
    headline: str
    body_snippet: str

    # --- Enrichment ---
    tickers: List[str] = Field(default_factory=list)
    event_class: Optional[EventClass] = None
    entities: List[str] = Field(default_factory=list)
    has_numbers: bool = False
    novel: bool = True

    # --- Scoring & Output ---
    materiality_score: int = 0
    summary: Optional[str] = None
    judge_scores: Dict[str, int] = Field(default_factory=dict)
    eligible_for_digest: bool = False
    eligible_for_alert: bool = False
    
    # --- Ensure UTC ---
    @field_validator("published_at", mode="after")
    def ensure_published_at_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)