"""v1.5b preset typography — apply spec §11.3 typography values

The v1.5.1 collapse migration seeded all 6 system presets at a uniform
``Georgia / 16 / 1.6 / 720`` baseline so each row had a stable starting
point. This migration walks each preset and updates its typography to
the spec §11.3 target values, but ONLY when the current row still equals
the original baseline tuple — preserving any user customization (FR-37,
NFR-06).

Idempotent: a second run finds zero rows still matching the baseline
because the first run already moved them to the targets.

Revision ID: 9a67312a27a7
Revises: e0c48efb7afe
Create Date: 2026-05-01 00:25:43
"""

from collections.abc import Sequence

import sqlalchemy as sa
import structlog
from alembic import op

logger = structlog.get_logger(__name__)

revision: str = "9a67312a27a7"
down_revision: str | None = "e0c48efb7afe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# (name, font_family, font_size_px, line_spacing, content_width_px, theme)
# Spec §11.3 — D10 typography combinations.
_TARGETS: list[tuple[str, str, int, float, int, str]] = [
    ("Light", "Georgia", 16, 1.6, 720, "light"),
    ("Sepia", "Georgia", 17, 1.7, 680, "sepia"),
    ("Dark", "Inter", 16, 1.6, 720, "dark"),
    ("Night", "Inter", 18, 1.7, 680, "night"),
    ("Paper", "Lora", 17, 1.8, 640, "paper"),
    ("High Contrast", "Inter", 18, 1.7, 700, "contrast"),
]

# Original baseline seeded by a5459240fea0_v1_5_1_collapse_reading_presets.
_BASELINE = ("Georgia", 16, 1.6, 720)


def upgrade() -> None:
    conn = op.get_bind()
    updated = 0
    for name, font, size, lh, width, theme in _TARGETS:
        result = conn.execute(
            sa.text(
                "UPDATE reading_presets "
                "SET font_family=:font, font_size_px=:size, line_spacing=:lh, "
                "    content_width_px=:width, theme=:theme "
                "WHERE name=:name "
                "AND font_family=:b_font AND font_size_px=:b_size "
                "AND line_spacing=:b_lh AND content_width_px=:b_width"
            ),
            {
                "name": name,
                "font": font,
                "size": size,
                "lh": lh,
                "width": width,
                "theme": theme,
                "b_font": _BASELINE[0],
                "b_size": _BASELINE[1],
                "b_lh": _BASELINE[2],
                "b_width": _BASELINE[3],
            },
        )
        if result.rowcount:
            updated += 1
    logger.info("v1_5b_preset_typography", updated=updated, total=len(_TARGETS))


def downgrade() -> None:  # pragma: no cover
    # Forward-only data migration. Reverting to the legacy baseline would
    # silently destroy the new spec values for users who never customized.
    pass
