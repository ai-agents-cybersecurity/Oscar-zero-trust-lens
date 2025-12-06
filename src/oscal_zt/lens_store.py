# src/oscal_zt/lens_store.py
"""
Persistence layer for Zero Trust lens annotations.

Allows saving and loading pre-computed ZT classifications
so you don't have to re-run the LLM for every analysis.
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from .config import ZT_LENS_PATH, ZT_LENS_DIR
from .models import ZTLens, AnnotatedControl


def ensure_lens_dir():
    """Ensure the lens storage directory exists."""
    ZT_LENS_DIR.mkdir(parents=True, exist_ok=True)


def save_lens(
    lens: ZTLens,
    path: Optional[str | Path] = None,
) -> Path:
    """
    Save a ZT lens to disk.
    
    Args:
        lens: The ZTLens to save
        path: Optional custom path (defaults to ZT_LENS_PATH)
        
    Returns:
        Path where the lens was saved
    """
    ensure_lens_dir()
    target = Path(path) if path else ZT_LENS_PATH
    
    # Add timestamp to metadata
    lens.metadata["saved_at"] = datetime.utcnow().isoformat()
    
    with open(target, "w", encoding="utf-8") as f:
        json.dump(lens.model_dump(), f, indent=2)
    
    return target


def load_lens(path: Optional[str | Path] = None) -> Optional[ZTLens]:
    """
    Load a ZT lens from disk.
    
    Args:
        path: Optional custom path (defaults to ZT_LENS_PATH)
        
    Returns:
        ZTLens if found, None otherwise
    """
    target = Path(path) if path else ZT_LENS_PATH
    
    if not target.exists():
        return None
    
    with open(target, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return ZTLens.model_validate(data)


def lens_exists(path: Optional[str | Path] = None) -> bool:
    """Check if a lens file exists."""
    target = Path(path) if path else ZT_LENS_PATH
    return target.exists()


def create_lens_from_annotated(
    annotated_controls: list[AnnotatedControl],
    catalog_source: str,
    model_used: str = "",
) -> ZTLens:
    """
    Create a ZTLens from a list of annotated controls.
    
    Args:
        annotated_controls: List of controls with ZT annotations
        catalog_source: Source catalog identifier
        model_used: LLM model used for classification
        
    Returns:
        ZTLens object ready to be saved
    """
    return ZTLens(
        catalog_source=catalog_source,
        annotated_controls=annotated_controls,
        metadata={
            "created_at": datetime.utcnow().isoformat(),
            "model_used": model_used,
            "control_count": str(len(annotated_controls)),
        },
    )
