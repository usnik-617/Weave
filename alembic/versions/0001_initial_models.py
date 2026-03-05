"""initial models

Revision ID: 0001_initial_models
Revises:
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_models"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("location", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("event_date", sa.String(length=40), nullable=False),
        sa.Column("max_participants", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("updated_at", sa.String(length=40), nullable=True),
    )

    op.create_table(
        "participants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.String(length=30), nullable=False, server_default="registered"
        ),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
    )

    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "is_important", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("publish_at", sa.String(length=40), nullable=True),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="published"
        ),
        sa.Column(
            "image_url", sa.String(length=500), nullable=False, server_default=""
        ),
        sa.Column(
            "thumb_url", sa.String(length=500), nullable=False, server_default=""
        ),
        sa.Column("volunteer_start_date", sa.String(length=40), nullable=True),
        sa.Column("volunteer_end_date", sa.String(length=40), nullable=True),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
    )

    op.create_table(
        "post_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("stored_path", sa.String(length=500), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column(
            "hash_sha256", sa.String(length=64), nullable=False, server_default=""
        ),
        sa.Column("expires_at", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.String(length=40), nullable=False),
    )

    op.create_table(
        "event_attendance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="registered"
        ),
        sa.Column("attended_at", sa.String(length=40), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "event_id", "user_id", name="uq_event_attendance_event_user"
        ),
    )

    op.create_table(
        "volunteer_activity",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.String(length=40), nullable=False),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column(
            "target_type", sa.String(length=50), nullable=False, server_default=""
        ),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("ip", sa.String(length=100), nullable=False, server_default=""),
        sa.Column(
            "user_agent", sa.String(length=500), nullable=False, server_default=""
        ),
        sa.Column("created_at", sa.String(length=40), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("volunteer_activity")
    op.drop_table("event_attendance")
    op.drop_table("post_files")
    op.drop_table("audit_logs")
    op.drop_table("posts")
    op.drop_table("participants")
    op.drop_table("events")
