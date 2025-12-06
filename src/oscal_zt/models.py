# src/oscal_zt/models.py
"""
Pydantic models for OSCAL Zero Trust Lens.

Defines the core data structures for:
- Control metadata extracted from OSCAL catalogs
- Zero Trust annotations (dimensions, criticality)
- Gap analysis reports
"""
from __future__ import annotations

from typing import List, Literal, Dict, Optional
from pydantic import BaseModel, Field


# Zero Trust dimensions based on NIST SP 800-207
ZTDimension = Literal[
    "identity",
    "device",
    "network",
    "application",
    "data",
    "visibility_analytics",
    "automation_orchestration",
]

# Criticality levels for Zero Trust alignment
ZTCriticality = Literal["core", "supporting", "optional"]


class ControlMeta(BaseModel):
    """Metadata for an OSCAL control."""

    control_id: str = Field(..., description="Control identifier (e.g., 'ac-1')")
    title: str = Field(..., description="Control title")
    family: Optional[str] = Field(None, description="Control family (e.g., 'ac' for Access Control)")
    text: str = Field(..., description="Control description/prose")


class ZTAnnotation(BaseModel):
    """Zero Trust classification for a control."""

    dimensions: List[ZTDimension] = Field(
        ..., description="Zero Trust dimensions this control applies to"
    )
    criticality: ZTCriticality = Field(
        ..., description="How critical this control is for Zero Trust"
    )
    rationale: str = Field(..., description="Explanation for the classification")


class AnnotatedControl(BaseModel):
    """A control with its Zero Trust annotation."""

    meta: ControlMeta
    zt: ZTAnnotation


class ZTGapItem(BaseModel):
    """A specific gap in Zero Trust coverage."""

    dimension: ZTDimension = Field(..., description="The ZT dimension with a gap")
    missing_controls: List[str] = Field(
        default_factory=list, description="Control IDs that are missing"
    )
    description: str = Field(..., description="Human-readable gap description")


class ZTReport(BaseModel):
    """Complete Zero Trust coverage report."""

    coverage_by_dimension: Dict[ZTDimension, float] = Field(
        ..., description="Coverage percentage (0-100) per dimension"
    )
    missing_core_controls: Dict[ZTDimension, List[str]] = Field(
        ..., description="Missing core controls per dimension"
    )
    gaps: List[ZTGapItem] = Field(default_factory=list, description="Detailed gap items")
    summary: str = Field(..., description="Narrative summary of ZT posture")


class ZTLens(BaseModel):
    """
    A complete Zero Trust lens - the cached classification of controls.
    Can be persisted to disk and reused.
    """

    catalog_source: str = Field(..., description="Source catalog path or identifier")
    annotated_controls: List[AnnotatedControl] = Field(
        default_factory=list, description="All annotated controls"
    )
    metadata: Dict[str, str] = Field(
        default_factory=dict, description="Additional metadata (e.g., model used, date)"
    )
