"""add download retry fields

Revision ID: aaa38023ddE71
Revises: AAA38023DD71
Create Date: 2025-12-20 02:00:00.000000

Hey future me - AUTO-RETRY FEATURE!

Diese Migration fügt alle Felder hinzu, die für automatisches Retry-Management
von fehlgeschlagenen Downloads benötigt werden:

1. retry_count: Wie oft wurde dieser Download bereits versucht?
2. max_retries: Wie oft maximal versuchen? (Default: 3)
3. next_retry_at: Wann ist der nächste Retry geplant?
4. last_error_code: Klassifizierter Fehlercode (für intelligentes Retry)

RETRY-FLOW:
1. Download schlägt fehl → status=FAILED, retry_count++, next_retry_at berechnet
2. RetrySchedulerWorker prüft alle 30s: status=FAILED & next_retry_at <= now & retry_count < max_retries
3. Wenn gefunden: status → WAITING, QueueDispatcherWorker übernimmt
4. Nach max_retries: Download bleibt FAILED (manuelles Retry möglich)

BACKOFF-FORMEL:
- Retry 1: 1 Minute
- Retry 2: 5 Minuten
- Retry 3: 15 Minuten

ERROR-CODES (last_error_code):
- timeout: Retryable nach Backoff
- source_offline: Retryable (User offline)
- network_error: Retryable
- file_not_found: NON-retryable
- user_blocked: NON-retryable
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'aaa38023ddE71'
down_revision = 'AAA38023DD71'  # Fixed: Was incorrectly pointing to zz37022bbC70
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === Download Retry Fields ===
    
    # Retry counter - wie oft wurde dieser Download versucht?
    op.add_column('downloads', sa.Column(
        'retry_count', 
        sa.Integer(), 
        nullable=False, 
        server_default='0'
    ))
    
    # Max retries - wie oft maximal versuchen?
    op.add_column('downloads', sa.Column(
        'max_retries', 
        sa.Integer(), 
        nullable=False, 
        server_default='3'
    ))
    
    # Next retry timestamp - wann ist der nächste Retry geplant?
    op.add_column('downloads', sa.Column(
        'next_retry_at', 
        sa.DateTime(timezone=True), 
        nullable=True
    ))
    
    # Last error code - klassifizierter Fehlercode
    op.add_column('downloads', sa.Column(
        'last_error_code', 
        sa.String(50), 
        nullable=True
    ))
    
    # Index für effiziente Retry-Scheduling-Abfragen
    # Dieser Index hilft dem RetrySchedulerWorker, retry-fähige Downloads schnell zu finden
    op.create_index(
        'ix_downloads_retry_scheduling',
        'downloads',
        ['status', 'retry_count', 'next_retry_at'],
        postgresql_where=sa.text("status = 'failed'")
    )
    
    # Index für failed downloads mit error_code (für Statistiken/Debugging)
    op.create_index(
        'ix_downloads_error_code',
        'downloads',
        ['last_error_code'],
        postgresql_where=sa.text("last_error_code IS NOT NULL")
    )


def downgrade() -> None:
    # Indexes entfernen
    op.drop_index('ix_downloads_error_code', table_name='downloads')
    op.drop_index('ix_downloads_retry_scheduling', table_name='downloads')
    
    # Columns entfernen
    op.drop_column('downloads', 'last_error_code')
    op.drop_column('downloads', 'next_retry_at')
    op.drop_column('downloads', 'max_retries')
    op.drop_column('downloads', 'retry_count')
