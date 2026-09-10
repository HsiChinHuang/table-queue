"""SQLAlchemy 2.0 models for TableQueue backend."""

from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    UUID,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WaitlistStatus(Enum):
    """Waitlist entry status enum."""

    WAITING = "WAITING"
    CALLED = "CALLED"
    SEATED = "SEATED"
    DONE = "DONE"
    NO_SHOW = "NO_SHOW"
    CANCELLED = "CANCELLED"


class TableStatus(Enum):
    """Table status enum."""

    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"
    CLEANING = "CLEANING"


class WaitlistSource(Enum):
    """Waitlist entry source enum."""

    CUSTOMER = "CUSTOMER"
    STAFF = "STAFF"


class CancelledReason(Enum):
    """Waitlist entry cancellation reason enum."""

    CUSTOMER = "CUSTOMER"
    STAFF = "STAFF"
    CLOSED_DAY = "CLOSED_DAY"
    RESET = "RESET"


class Restaurant(Base):
    """Restaurant model."""

    __tablename__ = "restaurants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    branches: Mapped[list["Branch"]] = relationship(
        back_populates="restaurant", cascade="all, delete-orphan"
    )


class Branch(Base):
    """Branch model."""

    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    restaurant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("restaurants.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Asia/Taipei"
    )
    business_day_cutoff_hour: Mapped[int] = mapped_column(
        Integer, nullable=False, default=4
    )
    open_time: Mapped[str] = mapped_column(String(10), nullable=False)
    close_time: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    restaurant: Mapped["Restaurant"] = relationship(
        back_populates="branches", foreign_keys=[restaurant_id]
    )
    tables: Mapped[list["Table"]] = relationship(
        back_populates="branch", cascade="all, delete-orphan"
    )
    waitlist_entries: Mapped[list["WaitlistEntry"]] = relationship(
        back_populates="branch", cascade="all, delete-orphan"
    )
    settings: Mapped["Settings"] = relationship(
        back_populates="branch", uselist=False, cascade="all, delete-orphan"
    )


class Table(Base):
    """Table model."""

    __tablename__ = "tables"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    branch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("branches.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[TableStatus] = mapped_column(
        SQLEnum(TableStatus), nullable=False, default=TableStatus.AVAILABLE
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    branch: Mapped["Branch"] = relationship(
        back_populates="tables", foreign_keys=[branch_id]
    )
    waitlist_entries: Mapped[list["WaitlistEntry"]] = relationship(
        back_populates="table"
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint("branch_id", "label", name="uq_branch_label"),
        Index("idx_table_branch_active_status", "branch_id", "is_active", "status"),
    )


class WaitlistEntry(Base):
    """WaitlistEntry model."""

    __tablename__ = "waitlist_entries"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    branch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("branches.id"), nullable=False
    )
    queue_number: Mapped[str] = mapped_column(String(20), nullable=False)
    full_queue_number: Mapped[str] = mapped_column(String(50), nullable=False)
    queue_prefix: Mapped[str] = mapped_column(String(10), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    business_date: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    party_size: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[WaitlistStatus] = mapped_column(
        SQLEnum(WaitlistStatus), nullable=False, default=WaitlistStatus.WAITING
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[WaitlistSource] = mapped_column(
        SQLEnum(WaitlistSource), nullable=False, default=WaitlistSource.CUSTOMER
    )
    hold_minutes_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cancelled_reason: Mapped[CancelledReason | None] = mapped_column(
        SQLEnum(CancelledReason), nullable=True
    )
    table_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tables.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    called_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    seated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    branch: Mapped["Branch"] = relationship(
        back_populates="waitlist_entries", foreign_keys=[branch_id]
    )
    table: Mapped["Table | None"] = relationship(
        back_populates="waitlist_entries", foreign_keys=[table_id]
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "branch_id", "business_date", "queue_prefix", "seq", name="uq_queue_seq"
        ),
        Index(
            "idx_waitlist_branch_date_status",
            "branch_id",
            "business_date",
            "status",
        ),
        Index("idx_waitlist_branch_sort_order", "branch_id", "sort_order"),
    )


class Settings(Base):
    """Settings model."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    branch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("branches.id"), nullable=False, unique=True
    )
    hold_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    avg_seat_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    queue_prefix: Mapped[str] = mapped_column(String(10), nullable=False, default="A")
    is_waitlist_open: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    sound_enabled_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    notification_templates: Mapped[dict] = mapped_column(
        String(2000), nullable=False, default=lambda: "{}"
    )
    staff_pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    branch: Mapped["Branch"] = relationship(
        back_populates="settings", foreign_keys=[branch_id]
    )
