"""CLI entrypoint for lakebase-assess."""

import json
import sys
from pathlib import Path
from typing import Optional

import click
import yaml

from src.config import AssessmentConfig, load_config
from src.engine.scoring import ScoreEngine
from src.engine.billing import BillingCalculator
from src.engine.classifier import WorkloadClassifier
from src.outputs.json_export import JsonExporter
from src.outputs.pdf_report import PdfReportGenerator
from src.outputs.checklist import ChecklistGenerator
from src.security.encryption import encrypt_payload
from src.security.privacy import sanitize_payload


@click.group()
@click.version_option(version="1.0.0")
def cli() -> None:
    """lakebase-assess: SQL-to-Databricks Lakebase migration assessment engine."""
    pass


@cli.command()
@click.option("--config", "config_path", type=click.Path(exists=True), default=None, help="Path to YAML config file.")
@click.option("--platform", "-p", "platforms", multiple=True, help="Platform(s) to assess (repeats allowed).")
@click.option("--output-dir", "-o", type=click.Path(), default="./assessment-output", help="Output directory for reports.")
@click.option("--anonymize", is_flag=True, default=False, help="Strip all PII before scoring.")
@click.option("--encrypt", is_flag=True, default=False, help="Encrypt local SQLite + JSON payload with AES-256.")
@click.option("--dry-run", is_flag=True, default=False, help="Validate config and connectors without executing queries.")
@click.option("--threshold", type=float, default=10.0, help="Minimum opportunity score to include in Priority list (default: 10).")
@click.option("--upload", is_flag=True, default=False, help="Enable optional anonymized upload to BPCS trend tracking.")
@click.pass_context
def run(
    ctx: click.Context,
    config_path: Optional[str],
    platforms: tuple[str, ...],
    output_dir: str,
    anonymize: bool,
    encrypt: bool,
    dry_run: bool,
    threshold: float,
    upload: bool,
) -> None:
    """Run the full assessment pipeline."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Load config
    cfg = load_config(config_path)
    if platforms:
        cfg.target_platforms = list(platforms)

    # Validate
    click.echo("Validating configuration and connector connectivity...")
    try:
        cfg.validate_connectors()
    except Exception as e:
        click.echo(click.style(f"Configuration error: {e}", fg="red"))
        ctx.exit(1)

    if dry_run:
        click.echo(click.style("Dry-run complete. No queries were executed.", fg="yellow"))
        return

    click.echo(f"Starting assessment for platforms: {', '.join(cfg.target_platforms)}")

    # Phase 1: Data ingestion via connectors
    scores: dict[str, dict] = {}
    payloads: dict[str, Any] = {}
    for platform in cfg.target_platforms:
        click.echo(f"\n  [{1 + list(cfg.target_platforms).index(platform)}/{len(cfg.target_platforms)}] Ingesting data from {platform}...")
        try:
            connector = cfg.get_connector(platform)
            payload = connector.ingest_all()
            payloads[platform] = payload
            click.echo(click.style(f"    Ingested {len(payload.query_history)} queries, {len(payload.table_metadata)} tables.", fg="green"))
        except Exception as e:
            click.echo(click.style(f"    Failed to connect to {platform}: {e}", fg="red"))
            continue

        # Phase 2: Privacy & sanitization
        if anonymize:
            payload = sanitize_payload(payload)
            click.echo(click.style("    Payload sanitized for PII.", fg="blue"))

        # Phase 3: Scoring
        score_engine = ScoreEngine(threshold=threshold)
        results = score_engine.score_payload(payload)
        click.echo(click.style(f"    Scored {len(results)} workloads. Priority: {sum(1 for r in results if r['opportunity_score'] >= 25)}", fg="green"))
        scores[platform] = results

    # Phase 4: Billing estimation
    billing = BillingCalculator(cfg.pricing_map_path)
    cost_deltas: dict[str, dict] = {}
    for platform, results in scores.items():
        click.echo(f"\n  Estimating costs for {platform}...")
        try:
            payload = payloads.get(platform)
            cost_signals = payload.cost_signals if payload else None
            display = payload.platform_display_name if payload else platform
            delta = billing.calculate_cost_delta(platform, display, cost_signals, results)
            cost_deltas[platform] = delta
            click.echo(click.style(f"    Current est.: ${delta['current_estimated_monthly_cost']:,.2f}/mo  |  "
                                   f"Projected: ${delta['projected_lakebase_cost']:,.2f}/mo  |  "
                                   f"Savings: {delta['savings_pct']:.1f}%", fg="green"))
        except Exception as e:
            click.echo(click.style(f"    Billing error for {platform}: {e}", fg="red"))

    # Phase 5: Workload classification
    classifier = WorkloadClassifier()
    buckets: dict[str, list[dict]] = {}
    for platform, results in scores.items():
        click.echo(f"\n  Classifying workloads for {platform}...")
        buckets[platform] = classifier.classify_all(results)
        for bucket_name, items in buckets[platform].items():
            click.echo(click.style(f"    {bucket_name}: {len(items)} workloads", fg="cyan"))

    # Phase 6: Generate outputs
    click.echo("\nGenerating outputs...")

    # PDF report
    pdf_gen = PdfReportGenerator(scores, cost_deltas, buckets)
    pdf_path = output_path / "executive.pdf"
    pdf_gen.generate(str(pdf_path))
    click.echo(click.style(f"  [PDF] {pdf_path}", fg="green"))

    # Dashboard HTML
    dashboard_path = output_path / "dashboard.html"
    pdf_gen.generate_dashboard(str(dashboard_path))
    click.echo(click.style(f"  [HTML] {dashboard_path}", fg="green"))

    # JSON export
    exporter = JsonExporter()
    json_path = output_path / "report.json"
    exporter.export(scores, cost_deltas, buckets, str(json_path))
    click.echo(click.style(f"  [JSON] {json_path}", fg="green"))

    # CSV export
    csv_path = output_path / "report.csv"
    exporter.export_csv(scores, str(csv_path))
    click.echo(click.style(f"  [CSV]  {csv_path}", fg="green"))

    # Checklist
    checklist_gen = ChecklistGenerator()
    checklist_path = output_path / "checklist.md"
    checklist_gen.generate(scores, buckets, str(checklist_path))
    click.echo(click.style(f"  [MD]   {checklist_path}", fg="green"))

    # Encryption
    if encrypt:
        encrypted_path = output_path / "payload.enc"
        key = encrypt_payload(str(json_path), str(encrypted_path))
        click.echo(click.style(f"  [ENC]  {encrypted_path} (key saved locally)", fg="green"))

    # Anonymized upload
    if upload:
        click.echo("\n  Preparing anonymized BPCS upload payload...")
        upload_payload = {}
        for platform, results in scores.items():
            avg_score = sum(r["opportunity_score"] for r in results) / max(len(results), 1)
            priority_1 = sum(1 for r in results if r["opportunity_score"] >= 25)
            platform_key = f"{hash(platform):x}"
            upload_payload[platform_key] = {
                "platform": platform_key,
                "avg_score": round(avg_score, 2),
                "priority_1_count": priority_1,
                "est_savings_pct": round(cost_deltas.get(platform, {}).get("savings_pct", 0), 1),
            }
        click.echo(click.style("  Upload payload prepared. Send to BPCS webhook when configured.", fg="blue"))
        click.echo(click.style("  (No external network call was made.)", fg="blue"))

    click.echo(click.style("\nAssessment complete. All data stored locally.", fg="green"))


@cli.command("validate")
@click.option("--config", "config_path", type=click.Path(exists=True), default=None)
@click.pass_context
def validate(ctx: click.Context, config_path: Optional[str]) -> None:
    """Validate config and connector connectivity without running assessment."""
    cfg = load_config(config_path)
    try:
        cfg.validate_connectors()
        click.echo(click.style("All connectors validated successfully.", fg="green"))
    except Exception as e:
        click.echo(click.style(f"Validation failed: {e}", fg="red"))
        ctx.exit(1)


@cli.command()
@click.option("--config", "config_path", type=click.Path(exists=True), default=None)
@click.pass_context
def upload(ctx: click.Context, config_path: Optional[str]) -> None:
    """Prepare and send anonymized assessment payload to BPCS trend tracking."""
    click.echo(click.style("Upload feature: no external network calls in this CLI.", fg="yellow"))
    click.echo("Review the generated payload in the output directory and configure your webhook URL manually.")
    ctx.forward(run)


if __name__ == "__main__":
    cli()
