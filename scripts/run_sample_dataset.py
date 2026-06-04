"""Run a sample integration dataset through the full pipeline.

Pipeline flow:
  - Ingest sample dataset
  - Run existing analyzers (OAuth, token, credential, data flow)
  - Run integration mapping
  - Run AI governance detection
  - Generate graph data
  - Apply risk scoring
  - Apply compliance mapping
  - Output final JSON and PDF artifacts

Usage:
  python scripts/run_sample_dataset.py                    # stdout summary only
  python scripts/run_sample_dataset.py --export out/      # write JSON + PDF to out/
  python scripts/run_sample_dataset.py --dataset data/sample_integrations.json
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure app is on path when run from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.scan_models import DatasetAnalysisRequest
from app.services.dataset_analysis import analyze_dataset
from app.services.pdf_report_generator import generate_executive_pdf
from app.services.rules_loader import load_rules


def main() -> int:
    parser = argparse.ArgumentParser(description="SaaSShadow dataset analysis with optional JSON/PDF export")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/sample_integrations.json"),
        help="Path to dataset JSON file",
    )
    parser.add_argument(
        "--export",
        type=Path,
        default=None,
        metavar="DIR",
        help="Export directory: write combined JSON report and per-integration PDFs",
    )
    args = parser.parse_args()

    if not args.dataset.exists():
        print(f"Error: dataset not found: {args.dataset}", file=sys.stderr)
        return 1

    payload = json.loads(args.dataset.read_text(encoding="utf-8"))
    request = DatasetAnalysisRequest.model_validate(payload)
    rules = load_rules(use_cache=False)
    result = analyze_dataset(request, rule_set=rules)

    print(f"\n{'=' * 72}")
    print(f"  SaaSShadow.ai — Dataset Analysis: {result.dataset_name}")
    print(f"{'=' * 72}\n")

    print(f"  Total integrations scanned:    {result.summary.total_integrations}")
    print(f"  High-risk integrations:        {result.summary.high_risk_integrations}")
    print(f"  Average risk score:            {result.summary.average_risk_score:.1f}")
    print(f"  OAuth over-permission hits:    {result.summary.oauth_over_permission_hits}")
    print(f"  Token misuse hits:             {result.summary.token_misuse_hits}")
    print(f"  Credential exposure hits:      {result.summary.credential_exposure_hits}")
    print(f"  Cross-platform risk hits:      {result.summary.cross_platform_risk_hits}")
    print()

    for item in result.results:
        level = item.risk_level
        bar = "#" * int(item.risk_score / 5)
        flags = []
        if item.oauth_over_permission_detected:
            flags.append("OAuth")
        if item.token_misuse_detected:
            flags.append("Token")
        if item.credential_exposure_detected:
            flags.append("Creds")
        if item.cross_platform_risk_detected:
            flags.append("DataFlow")
        flag_str = ", ".join(flags) if flags else "none"

        print(f"  {item.integration_id}")
        print(f"    Score: {item.risk_score:5.1f}  [{bar:<20}]  {level:<8}  risks: {flag_str}")
        # Show enterprise fields when present
        r = item.report
        if r and getattr(r, "integration_visibility_summary", None):
            sys_count = len((r.integration_visibility_summary or {}).get("systems", []))
            print(f"    Systems: {sys_count}  |  Graph edges: {len((r.risk_graph or {}).get('edges', []))}  |  Compliance mappings: {len(r.compliance_mapping or [])}")
        print()

    print(f"{'=' * 72}")

    # Export JSON and PDF when requested
    if args.export is not None:
        export_dir = args.export.resolve()
        export_dir.mkdir(parents=True, exist_ok=True)

        # Combined JSON: full dataset response (reports include executive_summary, risk_graph, compliance_mapping, etc.)
        combined = result.model_dump(mode="json")
        out_json = export_dir / "dataset_analysis_report.json"
        out_json.write_text(json.dumps(combined, indent=2, default=str), encoding="utf-8")
        print(f"\n  Exported: {out_json}")

        # Dataset context for "Dataset Context" section in each report (demo runs)
        dataset_context = {
            "dataset_name": result.dataset_name,
            "total_integrations": result.summary.total_integrations,
            "average_risk_score": round(result.summary.average_risk_score, 2),
            "credential_exposure_hits": result.summary.credential_exposure_hits,
            "token_misuse_hits": result.summary.token_misuse_hits,
            "oauth_over_permission_hits": result.summary.oauth_over_permission_hits,
            "cross_platform_risk_hits": result.summary.cross_platform_risk_hits,
        }
        # Per-integration PDFs (each report gets dataset context so PDF shows Dataset Context section)
        for i, item in enumerate(result.results):
            report_with_context = item.report.model_copy(
                update={"dataset_context": dataset_context}
            )
            pdf_bytes = generate_executive_pdf(report_with_context)
            safe_id = "".join(c if c.isalnum() or c in "_-" else "_" for c in item.integration_id)
            pdf_path = export_dir / f"report_{safe_id}.pdf"
            pdf_path.write_bytes(pdf_bytes)
            print(f"  Exported: {pdf_path}")

        # Summary JSON (smaller: summary + per-item scores and top risks only)
        summary_export = {
            "dataset_name": result.dataset_name,
            "summary": result.summary.model_dump(),
            "integrations": [
                {
                    "integration_id": item.integration_id,
                    "risk_score": item.risk_score,
                    "risk_level": item.risk_level,
                    "oauth_over_permission": item.oauth_over_permission_detected,
                    "token_misuse": item.token_misuse_detected,
                    "credential_exposure": item.credential_exposure_detected,
                    "cross_platform_risk": item.cross_platform_risk_detected,
                    "has_ai_risks": bool(getattr(item.report, "ai_data_flow_risks", None)),
                    "compliance_mapping_count": len(getattr(item.report, "compliance_mapping", None) or []),
                }
                for item in result.results
            ],
        }
        (export_dir / "dataset_summary.json").write_text(
            json.dumps(summary_export, indent=2), encoding="utf-8"
        )
        print(f"  Exported: {export_dir / 'dataset_summary.json'}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
