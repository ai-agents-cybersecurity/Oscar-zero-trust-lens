# src/oscal_zt/cli.py
"""
CLI entry point for OSCAL Zero Trust Lens.

Usage:
    python -m oscal_zt.cli [options]

Options:
    --json          Output report as JSON
    --verbose       Enable verbose logging
    --save-lens     Save the ZT lens to disk for reuse
    --catalog PATH  Custom catalog path
    --ssp PATH      Custom SSP path
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .graph import build_graph
from .oscal_loader import load_catalog_controls
from .config import OSCAL_CATALOG_PATH, DEMO_SSP_PATH, OPENAI_MODEL
from .lens_store import save_lens, create_lens_from_annotated


def setup_logging(verbose: bool = False):
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )


def print_report(report, as_json: bool = False):
    """Print the ZT report to stdout."""
    if as_json:
        print(json.dumps(report.model_dump(), indent=2))
        return
    
    print("\n" + "=" * 60)
    print("🔍 OSCAL Zero Trust Lens Report")
    print("=" * 60)
    
    print("\n📊 Zero Trust Coverage by Dimension")
    print("-" * 40)
    
    # Sort by coverage (lowest first to highlight gaps)
    sorted_dims = sorted(
        report.coverage_by_dimension.items(),
        key=lambda x: x[1]
    )
    
    for dim, pct in sorted_dims:
        # Visual bar
        bar_len = int(pct / 5)  # 20 chars max
        bar = "█" * bar_len + "░" * (20 - bar_len)
        
        # Status indicator
        if pct >= 75:
            status = "✅"
        elif pct >= 50:
            status = "⚠️"
        else:
            status = "❌"
        
        dim_display = dim.replace("_", " ").title()
        print(f"  {status} {dim_display:25} {bar} {pct:5.1f}%")
    
    print("\n🚨 Missing Core Controls")
    print("-" * 40)
    
    has_missing = False
    for dim, ctrls in report.missing_core_controls.items():
        if not ctrls:
            continue
        has_missing = True
        dim_display = dim.replace("_", " ").title()
        ctrl_list = ", ".join(ctrls[:5])  # Show first 5
        more = f" (+{len(ctrls) - 5} more)" if len(ctrls) > 5 else ""
        print(f"  • {dim_display}: {ctrl_list}{more}")
    
    if not has_missing:
        print("  ✅ No missing core controls in analyzed subset!")
    
    print("\n📝 Executive Summary")
    print("-" * 40)
    print(report.summary)
    
    if report.gaps:
        print("\n🎯 Detailed Gap Analysis")
        print("-" * 40)
        for g in report.gaps:
            dim_display = g.dimension.replace("_", " ").title()
            print(f"\n  [{dim_display}]")
            if g.missing_controls:
                print(f"    Missing: {', '.join(g.missing_controls[:5])}")
            print(f"    {g.description}")
    
    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="OSCAL Zero Trust Lens - Analyze your ZT posture from OSCAL documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m oscal_zt.cli
  python -m oscal_zt.cli --verbose --save-lens
  python -m oscal_zt.cli --json > report.json
  python -m oscal_zt.cli --catalog /path/to/catalog.json --ssp /path/to/ssp.json
        """,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output report as JSON",
    )
    parser.add_argument(
        "--markdown",
        nargs="?",
        const="-",
        help="Output report as Markdown (optionally provide a file path; defaults to stdout)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--save-lens",
        action="store_true",
        help="Save the ZT lens annotations to disk for reuse",
    )
    parser.add_argument(
        "--catalog",
        type=str,
        help="Path to custom OSCAL catalog (default: NIST SP 800-53 Rev 5)",
    )
    parser.add_argument(
        "--ssp",
        type=str,
        help="Path to custom OSCAL SSP",
    )
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    # Determine paths
    catalog_path = Path(args.catalog) if args.catalog else OSCAL_CATALOG_PATH
    ssp_path = Path(args.ssp) if args.ssp else DEMO_SSP_PATH
    
    # Check catalog exists
    if not catalog_path.exists():
        logger.error(f"Catalog not found: {catalog_path}")
        logger.info("Have you initialized the oscal-content submodule?")
        logger.info("Run: git submodule add https://github.com/usnistgov/oscal-content.git data/oscal-content")
        sys.exit(1)
    
    # Build and run graph
    logger.info(f"Loading catalog: {catalog_path}")
    logger.info(f"Using SSP: {ssp_path}")
    logger.info(f"LLM model: {OPENAI_MODEL}")
    
    graph = build_graph()
    
    # Pre-load controls
    try:
        controls = load_catalog_controls(catalog_path)
        logger.info(f"Loaded {len(controls)} controls from catalog")
    except Exception as e:
        logger.error(f"Failed to load catalog: {e}")
        sys.exit(1)
    
    state = {"controls": controls}
    if args.ssp:
        state["ssp_path"] = str(ssp_path)
    
    logger.info("Running Zero Trust analysis pipeline...")
    
    try:
        result = graph.invoke(state)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        sys.exit(1)
    
    report = result.get("zt_report")
    if not report:
        logger.error("No ZT report produced")
        sys.exit(1)
    
    # Optionally save the lens
    if args.save_lens:
        annotated = result.get("annotated_controls", [])
        if annotated:
            lens = create_lens_from_annotated(
                annotated_controls=annotated,
                catalog_source=str(catalog_path),
                model_used=OPENAI_MODEL,
            )
            saved_path = save_lens(lens)
            logger.info(f"Saved ZT lens to: {saved_path}")
    
    # Output report(s)
    if args.json:
        print(json.dumps(report.model_dump(), indent=2))

    if args.markdown:
        md = render_markdown(report)
        if args.markdown == "-" or args.markdown is None:
            print(md)
        else:
            Path(args.markdown).write_text(md, encoding="utf-8")
            logger.info(f"Markdown report written to {args.markdown}")

    if not args.json and not args.markdown:
        print_report(report, as_json=False)


def render_markdown(report) -> str:
    """Render the ZT report as Markdown."""
    lines = []
    lines.append("# OSCAL Zero Trust Lens Report")
    lines.append("")
    lines.append("## Summary")
    lines.append(report.summary)
    lines.append("")

    lines.append("## Coverage by Dimension")
    lines.append("")
    lines.append("| Dimension | Coverage |")
    lines.append("|-----------|----------|")
    for dim, pct in sorted(report.coverage_by_dimension.items(), key=lambda x: x[0]):
        lines.append(f"| {dim.replace('_', ' ').title()} | {pct:.1f}% |")
    lines.append("")

    lines.append("## Missing Core Controls")
    for dim, ctrls in report.missing_core_controls.items():
        dim_display = dim.replace("_", " ").title()
        if ctrls:
            lines.append(f"- **{dim_display}**: {', '.join(ctrls)}")
        else:
            lines.append(f"- **{dim_display}**: _None_")
    lines.append("")

    if report.gaps:
        lines.append("## Gap Analysis")
        for g in report.gaps:
            dim_display = g.dimension.replace("_", " ").title()
            missing = ", ".join(g.missing_controls) if g.missing_controls else "None listed"
            lines.append(f"### {dim_display}")
            lines.append(f"- Missing controls: {missing}")
            lines.append(f"- Notes: {g.description}")
            lines.append("")
    else:
        lines.append("## Gap Analysis")
        lines.append("_No detailed gaps provided._")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
