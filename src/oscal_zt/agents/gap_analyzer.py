# src/oscal_zt/agents/gap_analyzer.py
"""
Zero Trust Gap Analyzer Agent.

Computes coverage metrics per ZT dimension and identifies gaps
in the organization's Zero Trust posture based on implemented controls.
"""
from __future__ import annotations

from typing import Dict, Any, List, DefaultDict
from collections import defaultdict
import json
import logging

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from ..config import OPENAI_MODEL
from ..models import AnnotatedControl, ZTReport, ZTGapItem, ZTDimension, ZTCriticality

logger = logging.getLogger(__name__)

_llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0)

_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are a Zero Trust architect with deep expertise in NIST SP 800-207.

Given coverage data about implemented controls classified by Zero Trust dimension,
provide a concise, actionable gap analysis.

Focus on:
1. Which dimensions have the lowest coverage
2. Which missing CORE controls are most critical to address
3. Practical recommendations for improving ZT posture

Be specific and reference actual control IDs where relevant."""
        ),
        (
            "human",
            """Zero Trust coverage analysis data:

{coverage_json}

Provide a gap analysis. Return JSON with:
- "summary": A 2-3 paragraph executive summary of ZT posture
- "gaps": List of gap objects, each with:
  - "dimension": The ZT dimension
  - "missing_controls": List of critical missing control IDs
  - "description": Specific recommendations for this dimension

Focus on the most impactful gaps. JSON only."""
        ),
    ]
)


def gap_analyzer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node that produces the ZT gap analysis report.
    
    Input state:
        - annotated_controls: List of controls with ZT classifications
        - implemented_controls: Set of implemented control IDs
        
    Output state:
        - zt_report: Complete ZTReport with coverage and gaps
    """
    annotated: List[AnnotatedControl] = state.get("annotated_controls", [])
    implemented = state.get("implemented_controls", set())
    
    if not annotated:
        logger.warning("No annotated controls to analyze")
        return {}
    
    logger.info(f"Analyzing {len(annotated)} annotated controls against {len(implemented)} implemented")
    
    # Compute coverage by dimension and missing core controls
    counts_by_dim: DefaultDict[ZTDimension, int] = defaultdict(int)
    implemented_by_dim: DefaultDict[ZTDimension, int] = defaultdict(int)
    missing_core_by_dim: DefaultDict[ZTDimension, List[str]] = defaultdict(list)
    
    for ac in annotated:
        cid = ac.meta.control_id
        crit: ZTCriticality = ac.zt.criticality
        dims: List[ZTDimension] = ac.zt.dimensions
        
        for d in dims:
            counts_by_dim[d] += 1
            if cid in implemented:
                implemented_by_dim[d] += 1
            elif crit == "core":
                missing_core_by_dim[d].append(cid)
    
    # Calculate coverage percentages
    coverage_by_dim: Dict[ZTDimension, float] = {}
    for d, total in counts_by_dim.items():
        if total == 0:
            coverage_by_dim[d] = 0.0
        else:
            coverage_by_dim[d] = round(100.0 * implemented_by_dim[d] / total, 1)
    
    # Prepare payload for LLM
    coverage_payload = {
        "coverage_by_dimension": coverage_by_dim,
        "missing_core_controls": dict(missing_core_by_dim),
        "total_controls_analyzed": len(annotated),
        "total_implemented": len([
            ac for ac in annotated if ac.meta.control_id in implemented
        ]),
    }
    
    logger.info("Generating narrative gap analysis with LLM")
    
    messages = _PROMPT.format_messages(coverage_json=json.dumps(coverage_payload, indent=2))
    
    try:
        resp = _llm.invoke(messages)
        content = resp.content
        
        # Handle markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM response: {e}")
        parsed = {"summary": str(resp.content) if resp else "Analysis unavailable", "gaps": []}
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        parsed = {"summary": f"Analysis failed: {e}", "gaps": []}
    
    # Build gap items from LLM response
    gaps: List[ZTGapItem] = []
    for g in parsed.get("gaps", []):
        try:
            dim = g.get("dimension")
            # Validate dimension
            valid_dims = [
                "identity", "device", "network", "application",
                "data", "visibility_analytics", "automation_orchestration"
            ]
            if dim not in valid_dims:
                continue
            
            mi = g.get("missing_controls") or []
            desc = g.get("description") or ""
            gaps.append(
                ZTGapItem(
                    dimension=dim,  # type: ignore[arg-type]
                    missing_controls=mi,
                    description=desc,
                )
            )
        except Exception as e:
            logger.warning(f"Failed to parse gap item: {e}")
            continue
    
    # Build the final report
    report = ZTReport(
        coverage_by_dimension=coverage_by_dim,
        missing_core_controls={k: v for k, v in missing_core_by_dim.items()},
        gaps=gaps,
        summary=parsed.get("summary", ""),
    )
    
    logger.info("Gap analysis complete")
    
    return {"zt_report": report}
