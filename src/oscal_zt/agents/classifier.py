# src/oscal_zt/agents/classifier.py
"""
Zero Trust Classifier Agent.

Classifies OSCAL controls into Zero Trust dimensions and criticality levels
using an LLM with expert knowledge of NIST SP 800-53 and SP 800-207.
"""
from __future__ import annotations

from typing import Dict, Any, List
import json
import logging

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from ..config import OPENAI_MODEL, OSCAL_CATALOG_PATH
from ..models import ControlMeta, ZTAnnotation, AnnotatedControl
from ..oscal_loader import load_catalog_controls

logger = logging.getLogger(__name__)

_llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0)

_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are an expert in NIST SP 800-53 (Security and Privacy Controls) and NIST SP 800-207 (Zero Trust Architecture).

Your task is to classify each security control into Zero Trust dimensions and criticality levels.

## Zero Trust Dimensions (from NIST SP 800-207):

- **identity**: Controls related to user/service identity verification, authentication, MFA, identity governance, access management, and credential management.
- **device**: Controls related to device posture assessment, device health monitoring, endpoint security, asset inventory, and device compliance.
- **network**: Controls related to micro-segmentation, network access controls, secure communications, boundary protection, and network monitoring.
- **application**: Controls related to application-level security, secure development, API security, application access controls, and workload security.
- **data**: Controls related to data protection, encryption, data classification, data loss prevention, and information handling.
- **visibility_analytics**: Controls related to logging, monitoring, audit trails, security analytics, threat detection, and continuous diagnostics.
- **automation_orchestration**: Controls related to policy automation, security orchestration, automated response (SOAR), configuration management, and continuous compliance.

## Criticality Levels:

- **core**: Foundational to Zero Trust - these controls directly implement ZT principles (e.g., strong authentication, device posture checks, micro-segmentation, encryption at rest/transit, centralized policy enforcement). Missing these creates significant ZT gaps.
- **supporting**: Important enablers that strengthen ZT posture but are not the primary mechanisms (e.g., security training, vulnerability scanning, incident response planning).
- **optional**: Nice-to-have or context-specific controls that may enhance ZT but are not essential for baseline ZT architecture.

## Response Format:

Return STRICT JSON only - a list of objects with these fields:
- control_id: string
- dimensions: list of applicable ZT dimensions (can be multiple)
- criticality: "core" | "supporting" | "optional"
- rationale: brief explanation (1-2 sentences)

A control can map to multiple dimensions if it spans concerns (e.g., AC-2 Account Management touches identity and visibility_analytics)."""
        ),
        (
            "human",
            "Classify these controls:\n\n{controls_json}\n\nRespond with JSON only.",
        ),
    ]
)


# Batch size for LLM calls (to avoid token limits)
BATCH_SIZE = 40


def _classify_batch(controls: List[ControlMeta]) -> List[Dict[str, Any]]:
    """Classify a batch of controls using the LLM."""
    payload = [
        {
            "control_id": c.control_id,
            "title": c.title,
            "family": c.family,
            "text": c.text[:2000],  # Truncate to avoid huge prompts
        }
        for c in controls
    ]

    messages = _PROMPT.format_messages(controls_json=json.dumps(payload, indent=2))
    
    try:
        resp = _llm.invoke(messages)
        content = resp.content
        
        # Handle markdown code blocks in response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM response as JSON: {e}")
        return []
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return []


def classifier_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node that classifies controls into ZT dimensions.
    
    Input state:
        - controls (optional): List of ControlMeta to classify
        
    Output state:
        - controls: Original controls
        - annotated_controls: Controls with ZT annotations
    """
    # Load controls if not provided
    if "controls" in state and state["controls"]:
        controls: List[ControlMeta] = state["controls"]
    else:
        logger.info(f"Loading catalog from {OSCAL_CATALOG_PATH}")
        controls = load_catalog_controls(OSCAL_CATALOG_PATH)
    
    logger.info(f"Classifying {len(controls)} controls (batch size: {BATCH_SIZE})")
    
    # For demo, just process first batch
    # In production, you'd loop through all batches
    subset = controls[:BATCH_SIZE]
    parsed = _classify_batch(subset)
    
    # Build annotated controls
    annotated: List[AnnotatedControl] = []
    meta_by_id = {c.control_id: c for c in subset}
    
    for item in parsed:
        cid = item.get("control_id")
        meta = meta_by_id.get(cid)
        if not meta:
            continue
        
        dims = item.get("dimensions") or []
        # Validate dimensions
        valid_dims = [
            d for d in dims
            if d in (
                "identity", "device", "network", "application",
                "data", "visibility_analytics", "automation_orchestration"
            )
        ]
        
        crit = item.get("criticality", "supporting")
        if crit not in ("core", "supporting", "optional"):
            crit = "supporting"
        
        rationale = item.get("rationale", "")
        
        try:
            zt = ZTAnnotation(
                dimensions=valid_dims,  # type: ignore[arg-type]
                criticality=crit,  # type: ignore[arg-type]
                rationale=rationale,
            )
            annotated.append(AnnotatedControl(meta=meta, zt=zt))
        except Exception as e:
            logger.warning(f"Failed to create annotation for {cid}: {e}")
            continue
    
    logger.info(f"Successfully annotated {len(annotated)} controls")
    
    return {"controls": controls, "annotated_controls": annotated}
