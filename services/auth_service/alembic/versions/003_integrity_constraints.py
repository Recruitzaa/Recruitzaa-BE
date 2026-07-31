"""Harden role, company, and membership integrity.

Revision ID: 003
Revises: 002
Create Date: 2026-07-30
"""

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_users_primary_role",
        "users",
        ("primary_role IN ('CANDIDATE','EMPLOYER','EXPERT','EMPLOYEE','SUPER_ADMIN')"),
    )
    op.create_check_constraint(
        "ck_users_available_roles",
        "users",
        (
            "available_roles <@ "
            "ARRAY['CANDIDATE','EMPLOYER','EXPERT','EMPLOYEE','SUPER_ADMIN']::text[] "
            "AND cardinality(available_roles) > 0 "
            "AND primary_role = ANY(available_roles)"
        ),
    )
    op.create_check_constraint(
        "ck_companies_status",
        "companies",
        "status IN ('PENDING','VERIFIED','SUSPENDED')",
    )
    op.create_check_constraint(
        "ck_companies_plan",
        "companies",
        "plan IN ('FREE','PRO','ENTERPRISE')",
    )
    op.create_check_constraint(
        "ck_company_members_role",
        "company_members",
        "member_role IN ('OWNER','ADMIN','RECRUITER')",
    )
    op.execute(
        """
        CREATE TRIGGER companies_updated_at
        BEFORE UPDATE ON companies
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS companies_updated_at ON companies;")
    op.drop_constraint("ck_company_members_role", "company_members", type_="check")
    op.drop_constraint("ck_companies_plan", "companies", type_="check")
    op.drop_constraint("ck_companies_status", "companies", type_="check")
    op.drop_constraint("ck_users_available_roles", "users", type_="check")
    op.drop_constraint("ck_users_primary_role", "users", type_="check")
