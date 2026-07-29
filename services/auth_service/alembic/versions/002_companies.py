"""Add companies and employer memberships.

Revision ID: 002
Revises: 001
Create Date: 2026-07-30
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(255), unique=True),
        sa.Column("website", sa.Text()),
        sa.Column("industry", sa.String(120)),
        sa.Column("company_size", sa.String(80)),
        sa.Column("company_type", sa.String(80)),
        sa.Column("hq_location", sa.String(255)),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("plan", sa.String(20), nullable=False, server_default="FREE"),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
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
    op.create_index("ix_companies_name", "companies", ["name"])
    op.create_index("ix_companies_domain", "companies", ["domain"], unique=True)
    op.create_index("ix_companies_status", "companies", ["status"])

    op.create_table(
        "company_members",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "member_role",
            sa.String(20),
            nullable=False,
            server_default="RECRUITER",
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_company_members_company_id", "company_members", ["company_id"])


def downgrade() -> None:
    op.drop_table("company_members")
    op.drop_table("companies")
