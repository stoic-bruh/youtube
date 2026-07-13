"""SQLAlchemy ORM models for the Asset Intelligence Engine."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, JSON, Float, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AssetResult(Base):
    """Persisted asset record — one per (storyboard, scene, asset_kind) tuple."""
    __tablename__ = "asset_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    storyboard_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    scene_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    asset_kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider_asset_id: Mapped[str | None] = mapped_column(String, nullable=True)

    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    license: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")

    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    negative_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    aspect_ratio: Mapped[str | None] = mapped_column(String(20), nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    cost_estimate_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    generation_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    local_cache_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    logs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AssetResult id={self.id!r} kind={self.asset_kind!r} "
            f"provider={self.provider!r} status={self.status!r}>"
        )


class AssetCacheEntry(Base):
    """Content-addressed cache: prompt/query hash → asset location."""
    __tablename__ = "asset_cache"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    cache_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    asset_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    local_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    license: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"<AssetCacheEntry key={self.cache_key!r} provider={self.provider!r}>"


class AssetProviderMetadata(Base):
    """Runtime statistics per provider (hit-rate, avg cost, avg latency)."""
    __tablename__ = "asset_provider_metadata"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    provider_type: Mapped[str] = mapped_column(String(20), nullable=False)  # stock | generate | icon
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    total_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cache_hits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    supported_kinds: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    def __repr__(self) -> str:
        return f"<AssetProviderMetadata name={self.provider_name!r} type={self.provider_type!r}>"
