"""add blocklist table

Revision ID: bbb38024eeF72
Revises: aaa38023ddE71
Create Date: 2025-12-22 11:00:00.000000

Hey future me - SOURCE BLOCKING FEATURE!

Diese Migration erstellt die blocklist-Tabelle für das automatische Blockieren
von fehlgeschlagenen Download-Quellen.

PROBLEM:
Manche Quellen schlagen konsistent fehl (offline User, blockierte IPs, ungültige Dateien).
Ohne Blocklist verschwenden wir Zeit mit Retries von den gleichen schlechten Quellen.

LÖSUNG:
Nach 3 Fehlern von der gleichen username+filepath Kombination innerhalb von 24h
wird diese Quelle auto-blockiert. Zukünftige Suchen überspringen blockierte Quellen.

SCOPE-OPTIONEN:
- username: Blockiere ALLE Dateien von diesem User (für user_blocked Errors)
- filepath: Blockiere diese spezifische Datei von ALLEN Usern (für file_not_found)
- specific: Blockiere NUR diese Datei von diesem User (Default für die meisten Errors)

EXPIRY:
Blöcke laufen nach konfigurierbarer Zeit ab (Default: 7 Tage).
Das behandelt Fälle wo ein User sein Setup repariert oder wieder online kommt.

TABELLEN-STRUKTUR:
- id: Unique identifier
- username: Soulseek username (NULL für filepath-only Blöcke)
- filepath: Dateipfad auf dem Share (NULL für username-only Blöcke)
- scope: Was wird geblockt ('username', 'filepath', 'specific')
- reason: Error-Code der zum Block führte
- failure_count: Wie viele Fehler führten zum Block
- blocked_at: Wann wurde der Block erstellt
- expires_at: Wann läuft der Block ab (NULL = permanent)
- is_manual: True wenn User manuell blockiert hat

INDEXES:
- ix_blocklist_lookup: Fast lookup für aktive Blöcke während Suche
- uq_blocklist_source: Verhindert doppelte Einträge für gleiche username+filepath
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'bbb38024eeF72'
down_revision = 'aaa38023ddE71'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === Create Blocklist Table ===
    op.create_table(
        'blocklist',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('username', sa.String(255), nullable=True, index=True),
        sa.Column('filepath', sa.String(1024), nullable=True, index=True),
        sa.Column('scope', sa.String(20), nullable=False, server_default='specific'),
        sa.Column('reason', sa.String(100), nullable=True),
        sa.Column('failure_count', sa.Integer, nullable=False, server_default='3'),
        sa.Column('blocked_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column('is_manual', sa.Boolean, nullable=False, server_default=sa.false()),
        # Constraints
        sa.UniqueConstraint('username', 'filepath', name='uq_blocklist_source'),
        sa.CheckConstraint(
            'username IS NOT NULL OR filepath IS NOT NULL',
            name='ck_blocklist_has_target',
        ),
    )
    
    # Composite index for fast lookup during search
    # When checking if a source is blocked, we query by username AND filepath AND expires_at
    op.create_index(
        'ix_blocklist_lookup',
        'blocklist',
        ['username', 'filepath', 'expires_at'],
    )


def downgrade() -> None:
    # Drop index first
    op.drop_index('ix_blocklist_lookup', table_name='blocklist')
    
    # Drop table
    op.drop_table('blocklist')
