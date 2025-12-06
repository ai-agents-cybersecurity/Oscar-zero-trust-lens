# src/oscal_zt/graph.py
"""
LangGraph pipeline for OSCAL Zero Trust Lens.

Wires together the classifier, SSP mapper, and gap analyzer agents
into a sequential pipeline.

Pipeline flow:
    START -> classifier -> ssp_mapper -> gap_analyzer -> END
"""
from __future__ import annotations

from typing import List, Set
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END

from .models import ControlMeta, AnnotatedControl, ZTReport
from .agents.classifier import classifier_node
from .agents.ssp_mapper import ssp_mapper_node
from .agents.gap_analyzer import gap_analyzer_node


class ZTState(TypedDict, total=False):
    """
    State schema for the Zero Trust Lens pipeline.
    
    Attributes:
        controls: Raw controls from OSCAL catalog
        annotated_controls: Controls with ZT classifications
        implemented_controls: Control IDs from SSP
        zt_report: Final gap analysis report
        ssp_path: Optional custom SSP path
    """
    controls: List[ControlMeta]
    annotated_controls: List[AnnotatedControl]
    implemented_controls: Set[str]
    zt_report: ZTReport
    ssp_path: str


def build_graph():
    """
    Build and compile the LangGraph pipeline.
    
    Returns:
        Compiled StateGraph ready for invocation
    """
    g = StateGraph(ZTState)

    # Add agent nodes
    g.add_node("classifier", classifier_node)
    g.add_node("ssp_mapper", ssp_mapper_node)
    g.add_node("gap_analyzer", gap_analyzer_node)

    # Wire the pipeline: START -> classifier -> ssp_mapper -> gap_analyzer -> END
    g.add_edge(START, "classifier")
    g.add_edge("classifier", "ssp_mapper")
    g.add_edge("ssp_mapper", "gap_analyzer")
    g.add_edge("gap_analyzer", END)

    return g.compile()


def run_pipeline(
    controls: List[ControlMeta] | None = None,
    ssp_path: str | None = None,
) -> ZTReport | None:
    """
    Convenience function to run the full pipeline.
    
    Args:
        controls: Optional pre-loaded controls (loads from config if None)
        ssp_path: Optional custom SSP path (uses config default if None)
        
    Returns:
        ZTReport with coverage and gap analysis, or None if failed
    """
    graph = build_graph()
    
    state: dict = {}
    if controls:
        state["controls"] = controls
    if ssp_path:
        state["ssp_path"] = ssp_path
    
    result = graph.invoke(state)
    
    return result.get("zt_report")
