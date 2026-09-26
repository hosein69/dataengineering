# -*- coding: utf-8 -*-
"""موتور چیدمان قابل‌تنظیم."""
from __future__ import annotations

from .dragdrop import draggable_block_list
from .engine import (BlockSpec, REGISTRY, add_block, load_layout, move_block,
                     register, remove_block, render_layout, reorder_blocks,
                     save_layout, set_block_size, visible_blocks)
from .presets import AUDIENCES, AUDIENCE_LABELS, DEFAULT_LAYOUT

__all__ = [
    "BlockSpec", "REGISTRY", "register", "render_layout", "visible_blocks",
    "load_layout", "save_layout", "move_block", "set_block_size",
    "remove_block", "add_block", "reorder_blocks", "draggable_block_list",
    "DEFAULT_LAYOUT", "AUDIENCES", "AUDIENCE_LABELS",
]
