"""initial schema, category seed, dev user

Revision ID: 0001
Revises:
Create Date: 2026-09-16
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.extractor.schema import CATEGORIES, CATEGORY_LABELS

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_admin", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("settings_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "categories",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("label_tr", sa.String(), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False),
    )
    op.create_table(
        "statements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("bank", sa.String(), nullable=True),
        sa.Column("profile", sa.String(), nullable=True),
        sa.Column("statement_type", sa.String(), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("redaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mask_warnings_json", sa.Text(), nullable=True),
        sa.Column("validation_issues_json", sa.Text(), nullable=True),
        sa.Column("masked_sha256", sa.String(), nullable=False),
        sa.Column("model_used", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("thought_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd_micro", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stated_total_debit_kurus", sa.Integer(), nullable=True),
        sa.Column("extracted_total_debit_kurus", sa.Integer(), nullable=True),
        sa.UniqueConstraint("user_id", "masked_sha256", name="uq_user_masked_sha256"),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "statement_id",
            sa.Integer(),
            sa.ForeignKey("statements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("txn_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount_kurus", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default="TRY"),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("merchant_norm", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("is_installment", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("installment_no", sa.Integer(), nullable=True),
        sa.Column("installment_total", sa.Integer(), nullable=True),
        sa.Column("user_override_category", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_transactions_statement_id", "transactions", ["statement_id"])
    op.create_index("ix_transactions_user_id_txn_date", "transactions", ["user_id", "txn_date"])

    op.bulk_insert(
        sa.table(
            "users",
            sa.column("id", sa.Integer),
            sa.column("email", sa.String),
            sa.column("password_hash", sa.String),
            sa.column("is_active", sa.Integer),
            sa.column("is_admin", sa.Integer),
            sa.column("settings_json", sa.Text),
            sa.column("created_at", sa.DateTime),
        ),
        [
            {
                "id": 1,
                "email": "dev@local",
                "password_hash": "dev-placeholder",
                "is_active": 1,
                "is_admin": 0,
                "settings_json": None,
                "created_at": datetime.now(UTC).replace(tzinfo=None),
            }
        ],
    )
    op.bulk_insert(
        sa.table(
            "categories",
            sa.column("key", sa.String),
            sa.column("label_tr", sa.String),
            sa.column("sort", sa.Integer),
        ),
        [
            {"key": key, "label_tr": CATEGORY_LABELS[key], "sort": index}
            for index, key in enumerate(CATEGORIES)
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_user_id_txn_date", table_name="transactions")
    op.drop_index("ix_transactions_statement_id", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("statements")
    op.drop_table("categories")
    op.drop_table("users")
