"""Initial schema — users, user_profiles, user_fcm_tokens

Revision ID: 001
Revises:
Create Date: 2026-07-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("firebase_uid", sa.String(128), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column(
            "primary_role", sa.String(20), nullable=False, server_default="CANDIDATE"
        ),
        sa.Column(
            "available_roles",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("ARRAY['CANDIDATE']::text[]"),
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_users_firebase_uid", "users", ["firebase_uid"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_primary_role", "users", ["primary_role"])

    # ── user_profiles ─────────────────────────────────────────────────────────
    op.create_table(
        "user_profiles",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("display_name", sa.String(255)),
        sa.Column("phone", sa.String(30)),
        sa.Column("photo_url", sa.Text()),
        sa.Column("location", sa.String(255)),
        sa.Column("bio", sa.Text()),
        sa.Column("summary", sa.Text()),  # AppUser.summary
        sa.Column("notice_period", sa.String(50)),  # AppUser.noticePeriod
        sa.Column("is_employed", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("current_company", sa.String(255)),
        sa.Column("current_role", sa.String(255)),
        sa.Column("current_salary", sa.String(50)),
    )

    # ── user_fcm_tokens ───────────────────────────────────────────────────────
    op.create_table(
        "user_fcm_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.Text(), nullable=False, unique=True),
        sa.Column("platform", sa.String(20), nullable=False, server_default="web"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_user_fcm_tokens_user_id", "user_fcm_tokens", ["user_id"])

    # ── updated_at auto-update trigger ────────────────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    op.execute("""
        CREATE TRIGGER users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS users_updated_at ON users;")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column;")
    op.drop_table("user_fcm_tokens")
    op.drop_table("user_profiles")
    op.drop_table("users")
