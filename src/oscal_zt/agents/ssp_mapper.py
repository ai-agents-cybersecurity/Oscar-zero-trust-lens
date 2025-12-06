# src/oscal_zt/agents/ssp_mapper.py
"""
SSP Mapper Agent.

Loads an OSCAL System Security Plan and extracts the set of
implemented control IDs for comparison against the ZT lens.
"""
from __future__ import annotations

from typing import Dict, Any, Set
import logging

from ..config import DEMO_SSP_PATH
from ..oscal_loader import extract_implemented_controls_from_ssp

logger = logging.getLogger(__name__)


def ssp_mapper_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node that extracts implemented controls from an SSP.
    
    Input state:
        - ssp_path (optional): Path to SSP file (defaults to DEMO_SSP_PATH)
        
    Output state:
        - implemented_controls: Set of control IDs that are implemented
    """
    ssp_path = state.get("ssp_path", DEMO_SSP_PATH)
    
    logger.info(f"Loading SSP from {ssp_path}")
    
    try:
        implemented: Set[str] = extract_implemented_controls_from_ssp(ssp_path)
        logger.info(f"Found {len(implemented)} implemented controls in SSP")
    except FileNotFoundError:
        logger.warning(f"SSP file not found: {ssp_path}")
        implemented = set()
    except Exception as e:
        logger.error(f"Failed to load SSP: {e}")
        implemented = set()
    
    return {"implemented_controls": implemented}
