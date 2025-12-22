"""add background jobs table

Revision ID: ccc38025ffG73
Revises: bbb38024eeF72
Create Date: 2025-12-22 12:00:00.000000

Hey future me - JOB PERSISTENZ!

Diese Migration erstellt die background_jobs Tabelle für persistente Job-Speicherung.

PROBLEM:
In-Memory JobQueue verliert alle Jobs bei App-Neustart.
User queued 50 Album-Downloads, Container startet neu, alles weg!

LÖSUNG:
Jobs werden in der DB gespeichert und beim Startup geladen.
Jobs überleben Neustarts, Worker machen dort weiter wo sie aufgehört haben.

WORKER LOCKING:
- Mehrere Worker können laufen (horizontale Skalierung)
- locked_by + locked_at verhindern Race Conditions
- Stale Lock Detection: Wenn locked_at > 5min und noch RUNNING, ist Worker abgestürzt

TABELLEN-STRUKTUR:
- id: Unique identifier
- job_type: download, library_scan, metadata_enrichment, etc.
- status: pending, running, completed, failed, cancelled
- priority: Higher = processed first (default 0)
- payload: JSON mit Job-Daten (Track-Info, Settings, etc.)
- result: JSON mit Ergebnis (Erfolg, Progress, etc.)
- error: Fehlermeldung wenn failed
- retries: Anzahl Retry-Versuche
- max_retries: Maximum Retries (default 3)
- created_at: Wann erstellt
- started_at: Wann gestartet
- completed_at: Wann fertig (oder failed)
- locked_by: Worker-ID der den Job bearbeitet
- locked_at: Wann gelockt
- next_run_at: Für scheduled/delayed Jobs

INDEXES:
- ix_jobs_pending: Status + Priority + Created für schnelle Pending-Abfrage
- ix_jobs_locked: Für Stale Lock Detection
- ix_jobs_scheduled: Für scheduled Jobs
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ccc38025ffG73'
down_revision = 'bbb38024eeF72'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === Create Background Jobs Table ===
    op.create_table(
        'background_jobs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('job_type', sa.String(50), nullable=False, index=True),
        sa.Column('status', sa.String(20), nullable=False, index=True),
        sa.Column('priority', sa.Integer, nullable=False, server_default='0', index=True),
        sa.Column('payload', sa.Text, nullable=False),
        sa.Column('result', sa.Text, nullable=True),
        sa.Column('error', sa.Text, nullable=True),
        sa.Column('retries', sa.Integer, nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer, nullable=False, server_default='3'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('locked_by', sa.String(100), nullable=True),
        sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True, index=True),
    )
    
    # Composite indexes for efficient querying
    op.create_index(
        'ix_jobs_pending',
        'background_jobs',
        ['status', 'priority', 'created_at'],
    )
    op.create_index(
        'ix_jobs_locked',
        'background_jobs',
        ['locked_by', 'locked_at'],
    )
    op.create_index(
        'ix_jobs_scheduled',
        'background_jobs',
        ['next_run_at', 'status'],
    )


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('ix_jobs_scheduled', table_name='background_jobs')
    op.drop_index('ix_jobs_locked', table_name='background_jobs')
    op.drop_index('ix_jobs_pending', table_name='background_jobs')
    
    # Drop table
    op.drop_table('background_jobs')
