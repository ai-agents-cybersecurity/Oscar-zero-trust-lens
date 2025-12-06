# src/oscal_zt/oscal_loader.py
"""
OSCAL document loaders for catalogs and SSPs.

Handles loading and parsing OSCAL JSON documents into our internal models.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List, Set

from .models import ControlMeta


def load_json(path: str | Path) -> Dict[str, Any]:
    """Load a JSON file and return its contents."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _extract_control_text(control: Dict[str, Any]) -> str:
    """Extract text/prose from a control's parts."""
    title = control.get("title", "")
    parts = control.get("parts", [])
    text_parts: List[str] = []
    
    if title:
        text_parts.append(title)
    
    for p in parts:
        prose = p.get("prose")
        if prose:
            text_parts.append(prose)
        # Handle nested parts (e.g., guidance)
        for nested in p.get("parts", []):
            nested_prose = nested.get("prose")
            if nested_prose:
                text_parts.append(nested_prose)
    
    return "\n\n".join(text_parts)


def _extract_controls_recursive(
    controls: List[Dict[str, Any]], family: str | None = None
) -> List[ControlMeta]:
    """Recursively extract controls, including enhancements."""
    result: List[ControlMeta] = []
    
    for ctl in controls:
        cid = ctl.get("id")
        title = ctl.get("title", "")
        text = _extract_control_text(ctl)
        
        if cid:
            result.append(
                ControlMeta(control_id=cid, title=title, family=family, text=text)
            )
        
        # Handle control enhancements (nested controls)
        enhancements = ctl.get("controls", [])
        if enhancements:
            result.extend(_extract_controls_recursive(enhancements, family=family))
    
    return result


def load_catalog_controls(path: str | Path) -> List[ControlMeta]:
    """
    Load an OSCAL catalog (e.g., SP 800-53) and flatten into ControlMeta records.
    
    Assumes structure of OSCAL catalog model v1.x.
    Handles both grouped controls (by family) and top-level controls.
    
    Args:
        path: Path to the OSCAL catalog JSON file
        
    Returns:
        List of ControlMeta objects for all controls in the catalog
    """
    raw = load_json(path)
    catalog = raw.get("catalog", raw)
    controls: List[ControlMeta] = []

    # Controls are often grouped by 'groups' (families)
    for group in catalog.get("groups", []):
        family = group.get("id")
        group_controls = group.get("controls", [])
        controls.extend(_extract_controls_recursive(group_controls, family=family))
    
    # Some catalogs may have top-level controls outside groups
    top_level = catalog.get("controls", [])
    if top_level:
        controls.extend(_extract_controls_recursive(top_level, family=None))

    return controls


def extract_implemented_controls_from_ssp(path: str | Path) -> Set[str]:
    """
    Extract implemented control IDs from an OSCAL SSP.
    
    For v0, treat any control-id present in implemented-requirements as 'implemented'.
    You can refine to look at implementation status later.
    
    Args:
        path: Path to the OSCAL SSP JSON file
        
    Returns:
        Set of implemented control IDs
    """
    raw = load_json(path)
    ssp = raw.get("system-security-plan", raw)
    impl = ssp.get("control-implementation", {})
    reqs = impl.get("implemented-requirements", [])

    implemented: Set[str] = set()
    for r in reqs:
        cid = r.get("control-id")
        if cid:
            implemented.add(cid)

    return implemented


def load_profile_controls(path: str | Path) -> Set[str]:
    """
    Load an OSCAL profile and extract the control IDs it includes.
    
    Profiles reference controls from catalogs and can include/exclude them.
    This is useful for baseline profiles (e.g., LOW, MODERATE, HIGH).
    
    Args:
        path: Path to the OSCAL profile JSON file
        
    Returns:
        Set of control IDs included in the profile
    """
    raw = load_json(path)
    profile = raw.get("profile", raw)
    imports = profile.get("imports", [])
    
    included: Set[str] = set()
    
    for imp in imports:
        include_controls = imp.get("include-controls", [])
        for inc in include_controls:
            with_ids = inc.get("with-ids", [])
            included.update(with_ids)
    
    return included
