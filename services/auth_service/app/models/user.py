"""
Auth Service SQLAlchemy ORM models.
Maps to: users, user_profiles, user_fcm_tokens PostgreSQL tables.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from shared.database.postgres import Base


def _now():
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firebase_uid = Column(String(128), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    primary_role = Column(String(20), nullable=False, default="CANDIDATE")
    available_roles = Column(
        ARRAY(Text),
        nullable=False,
        default=lambda: ["CANDIDATE"],
    )
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    # Relationships
    profile = relationship(
        "UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    fcm_tokens = relationship(
        "UserFCMToken", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User id={self.id} email={self.email} role={self.primary_role}>"


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    display_name = Column(String(255))
    phone = Column(String(30))
    photo_url = Column(Text)
    location = Column(String(255))
    bio = Column(Text)
    summary = Column(Text)          # AppUser.summary
    notice_period = Column(String(50))  # AppUser.noticePeriod
    is_employed = Column(Boolean, default=False)  # AppUser.isCurrentlyEmployed
    current_company = Column(String(255))   # AppUser.currentCompany
    current_role = Column(String(255))      # AppUser.currentRole
    current_salary = Column(String(50))     # AppUser.currentSalary

    user = relationship("User", back_populates="profile")

    def __repr__(self):
        return f"<UserProfile user_id={self.user_id} name={self.display_name}>"


class UserFCMToken(Base):
    __tablename__ = "user_fcm_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token = Column(Text, nullable=False, unique=True)
    platform = Column(String(20), nullable=False, default="web")  # web | android | ios
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    user = relationship("User", back_populates="fcm_tokens")

    def __repr__(self):
        return f"<UserFCMToken user_id={self.user_id} platform={self.platform}>"
