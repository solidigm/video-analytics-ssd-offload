# Created by Metrum AI for Solidigm

"""SQLAlchemy models for Sports Analytics Platform."""

# pylint: disable=too-few-public-methods

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    BigInteger,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Video(Base):
    """Video metadata model."""

    __tablename__ = "videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    original_path = Column(Text)
    file_size_bytes = Column(BigInteger)
    duration_seconds = Column(Float)
    frame_count = Column(Integer)
    width = Column(Integer)
    height = Column(Integer)
    fps = Column(Float)
    status = Column(String(50), default="pending", index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    analyses = relationship("Analysis", back_populates="video", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="video")
    telemetry_records = relationship("Telemetry", back_populates="video")

    def to_dict(self) -> dict:
        """Serialize the video model into a JSON-safe dictionary."""
        return {
            "id": str(self.id),
            "filename": self.filename,
            "original_path": self.original_path,
            "file_size_bytes": self.file_size_bytes,
            "duration_seconds": self.duration_seconds,
            "frame_count": self.frame_count,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Analysis(Base):
    """Video analysis result model."""

    __tablename__ = "analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    query = Column(Text, nullable=False)
    analysis_type = Column(String(50), default="general")
    coaching_report = Column(Text)
    duration_seconds = Column(Float)
    llm_model = Column(String(100))
    vlm_model = Column(String(100))
    total_frames_analyzed = Column(Integer)
    status = Column(String(50), default="pending", index=True)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    video = relationship("Video", back_populates="analyses")
    chat_sessions = relationship("ChatSession", back_populates="analysis")
    telemetry_records = relationship("Telemetry", back_populates="analysis")

    def to_dict(self) -> dict:
        """Serialize the analysis model into a JSON-safe dictionary."""
        return {
            "id": str(self.id),
            "video_id": str(self.video_id),
            "query": self.query,
            "analysis_type": self.analysis_type,
            "coaching_report": self.coaching_report,
            "duration_seconds": self.duration_seconds,
            "llm_model": self.llm_model,
            "vlm_model": self.vlm_model,
            "total_frames_analyzed": self.total_frames_analyzed,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ChatSession(Base):
    """Chat interaction model."""

    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="SET NULL"), index=True)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="SET NULL"), index=True)
    query = Column(Text, nullable=False)
    response = Column(Text)
    llm_target = Column(String(50), nullable=False, default="lmcache")
    latency_ms = Column(Float)
    tokens_prompt = Column(Integer)
    tokens_completion = Column(Integer)
    tokens_total = Column(Integer)
    cache_hit = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    analysis = relationship("Analysis", back_populates="chat_sessions")
    video = relationship("Video", back_populates="chat_sessions")
    telemetry_records = relationship("Telemetry", back_populates="chat_session")

    def to_dict(self) -> dict:
        """Serialize the chat session model into a JSON-safe dictionary."""
        return {
            "id": str(self.id),
            "analysis_id": str(self.analysis_id) if self.analysis_id else None,
            "video_id": str(self.video_id) if self.video_id else None,
            "query": self.query,
            "response": self.response,
            "llm_target": self.llm_target,
            "latency_ms": self.latency_ms,
            "tokens_prompt": self.tokens_prompt,
            "tokens_completion": self.tokens_completion,
            "tokens_total": self.tokens_total,
            "cache_hit": self.cache_hit,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Telemetry(Base):
    """Agent telemetry model."""

    __tablename__ = "telemetry"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(String(64))
    span_id = Column(String(32))
    parent_span_id = Column(String(32))
    operation_name = Column(String(100), nullable=False)
    operation_type = Column(String(50), index=True)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="SET NULL"), index=True)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="SET NULL"))
    chat_session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="SET NULL"))
    duration_ms = Column(Float)
    status = Column(String(20))
    attributes = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    video = relationship("Video", back_populates="telemetry_records")
    analysis = relationship("Analysis", back_populates="telemetry_records")
    chat_session = relationship("ChatSession", back_populates="telemetry_records")

    def to_dict(self) -> dict:
        """Serialize telemetry into a JSON-safe dictionary."""
        return {
            "id": str(self.id),
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation_name": self.operation_name,
            "operation_type": self.operation_type,
            "video_id": str(self.video_id) if self.video_id else None,
            "analysis_id": str(self.analysis_id) if self.analysis_id else None,
            "chat_session_id": str(self.chat_session_id) if self.chat_session_id else None,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "attributes": self.attributes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
