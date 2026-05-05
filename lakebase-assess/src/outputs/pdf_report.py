"""Executive PDF report generator using reportlab."""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class PdfReportGenerator:
    """Generate executive PDF brief from assessment results."""

    def __init__(
        self,
        scores: dict[str, list[Any]],
        cost_deltas: dict[str, dict[str, Any]],
        buckets: dict[str, list[dict[str, Any]]],
    ) -> None:
        self.scores = scores
        self.cost_deltas = cost_deltas
        self.buckets = buckets

    def generate(self, output_path: str) -> str:
        """Generate the executive PDF report."""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib.colors import HexColor, black, white, grey
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
                HRFlowable, KeepTogether,
            )
        except ImportError:
            raise ImportError("reportlab is required for PDF generation. Install with: pip install reportlab")

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
        )

        styles = getSampleStyleSheet()
        elements: list = []

        # Title
        title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=24, spaceAfter=6)
        elements.append(Paragraph("Lakebase Migration Assessment Report", title_style))

        subtitle_style = ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=11, textColor=grey)
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", subtitle_style))
        elements.append(Spacer(1, 12))
        elements.append(HRFlowable(width="100%", thickness=1, color=grey))
        elements.append(Spacer(1, 12))

        # Executive summary per platform
        summary_style = ParagraphStyle("Summary", fontSize=12, spaceBefore=6, spaceAfter=6)
        elements.append(Paragraph("Executive Summary", styles["Heading2"]))

        for platform, platform_scores in self.scores.items():
            delta = self.cost_deltas.get(platform, {})
            platform_key = delta.get("platform_key", platform)

            elements.append(Paragraph(f"<b>{delta.get('platform', platform)}</b>", styles["Heading3"]))

            total = len(platform_scores)
            priority_1 = sum(1 for s in platform_scores if hasattr(s, "adjusted_score") and s.adjusted_score >= 25)
            avg_score = sum(getattr(s, "adjusted_score", 0) for s in platform_scores) / max(total, 1)
            savings = delta.get("savings_pct", 0)
            current_cost = delta.get("current_estimated_monthly_cost", 0)
            projected_cost = delta.get("projected_lakebase_cost", 0)

            summary_text = (
                f"<ul>"
                f"<li>Total workloads assessed: {total}</li>"
                f"<li>Priority 1 migration targets: {priority_1}</li>"
                f"<li>Average opportunity score: {avg_score:.1f}</li>"
                f"<li>Estimated current cost: ${current_cost:,.2f}/mo</li>"
                f"<li>Projected Lakebase cost: ${projected_cost:,.2f}/mo</li>"
                f"<li>Estimated savings: {savings:.1f}%</li>"
                f"</ul>"
            )
            elements.append(Paragraph(summary_text, styles["Normal"]))
            elements.append(Spacer(1, 6))

        # Scorecard table
        elements.append(Paragraph("Scorecard", styles["Heading2"]))

        score_data: list[list] = [["Workload", "Pain", "Impact", "Complexity", "Score", "Priority", "Bucket"]]
        for platform, platform_scores in self.scores.items():
            for s in platform_scores:
                adjusted = getattr(s, "adjusted_score", 0)
                priority = getattr(s, "priority", "Hold")
                bucket = getattr(s, "classification", "Unknown")
                identifier = getattr(s, "identifier", "")[:30]
                score_data.append([
                    identifier,
                    str(getattr(s, "pain", 0)),
                    str(getattr(s, "business_impact", 0)),
                    str(getattr(s, "complexity", 0)),
                    f"{adjusted:.1f}",
                    priority,
                    bucket[:20],
                ])

        col_widths = [80, 30, 35, 40, 45, 60, 80]
        score_table = Table(score_data, colWidths=col_widths)
        score_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1a1a2e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#f8f8f8")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(score_table)
        elements.append(Spacer(1, 18))

        # Cost delta table
        if self.cost_deltas:
            elements.append(Paragraph("Cost Comparison", styles["Heading2"]))
            cost_data: list[list] = [["Platform", "Current ($/mo)", "Projected ($/mo)", "Savings (%)"]]
            for platform, delta in self.cost_deltas.items():
                cost_data.append([
                    delta.get("platform", platform),
                    f"${delta.get('current_estimated_monthly_cost', 0):,.2f}",
                    f"${delta.get('projected_lakebase_cost', 0):,.2f}",
                    f"{delta.get('savings_pct', 0):.1f}%",
                ])
            cost_table = Table(cost_data, colWidths=[100, 90, 90, 60])
            cost_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1a1a2e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#f8f8f8")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            elements.append(cost_table)
            elements.append(Spacer(1, 18))

        # Migration buckets
        elements.append(Paragraph("Migration Buckets", styles["Heading2"]))
        for bucket_name, items in self.buckets.items():
            if not items:
                continue
            elements.append(Paragraph(f"<b>{bucket_name}</b>", styles["Heading3"]))
            for item in items:
                ident = item.get("identifier", "unknown")[:40]
                sc = item.get("adjusted_score", 0)
                elements.append(Paragraph(f"&bull; {ident} (score: {sc:.1f})", styles["Normal"]))
            elements.append(Spacer(1, 6))

        # Build PDF
        doc.build(elements)
        return output_path

    def generate_dashboard(self, output_path: str) -> str:
        """Generate an interactive HTML dashboard with Plotly charts."""
        import plotly.graph_objects as go
        import plotly.express as px
        from plotly.subplots import make_subplots

        # Gather all scores
        all_scores: list[dict[str, Any]] = []
        for platform, scores in self.scores.items():
            for s in scores:
                if hasattr(s, "identifier"):
                    all_scores.append({
                        "platform": platform,
                        "identifier": getattr(s, "identifier", "")[:25],
                        "adjusted_score": getattr(s, "adjusted_score", 0),
                        "pain": getattr(s, "pain", 0),
                        "business_impact": getattr(s, "business_impact", 0),
                        "complexity": getattr(s, "complexity", 0),
                        "priority": getattr(s, "priority", "Hold"),
                        "classification": getattr(s, "classification", ""),
                    })

        if not all_scores:
            # Generate minimal HTML
            html = """<!DOCTYPE html><html><head><title>Lakebase Dashboard</title></head>
            <body><h1>No data to display</h1></body></html>"""
            with open(output_path, "w") as f:
                f.write(html)
            return output_path

        # Score distribution per platform
        platform_scores: dict[str, list[float]] = {}
        for s in all_scores:
            platform_scores.setdefault(s["platform"], []).append(s["adjusted_score"])

        fig = go.Figure()
        colors = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A", "#19D3F3", "#FF6692", "#B6E880", "#FF98A9", "#56CA00"]
        for i, (platform, scores) in enumerate(platform_scores.items()):
            fig.add_trace(go.Box(y=scores, name=platform, marker_color=colors[i % len(colors)]))

        fig.update_layout(
            title="Lakebase Opportunity Score Distribution by Platform",
            yaxis_title="Adjusted Opportunity Score",
            height=400,
            margin=dict(l=40, r=40, t=60, b=40),
        )
        html = fig.to_html(full_html=False, include_plotlyjs="cdn")

        # Add heatmap: Pain vs Impact
        heat_data: dict[tuple[int, int], int] = {}
        for s in all_scores:
            key = (s["pain"], s["business_impact"])
            heat_data[key] = heat_data.get(key, 0) + 1

        z_data = []
        x_labels = [1, 2, 3, 4, 5]
        for pain in range(1, 6):
            row = []
            for impact in range(1, 6):
                row.append(heat_data.get((pain, impact), 0))
            z_data.append(row)

        fig2 = go.Figure(data=go.Heatmap(z=z_data, x=[f"Impact {i}" for i in x_labels], y=[f"Pain {i}" for i in x_labels], colorscale="Blues"))
        fig2.update_layout(title="Pain vs Business Impact Heatmap", height=400, margin=dict(l=60, r=20, t=40, b=40))
        html += "<br>" + fig2.to_html(full_html=False, include_plotlyjs="cdn")

        # Priority breakdown donut chart
        priority_counts: dict[str, int] = {}
        for s in all_scores:
            priority_counts[s["priority"]] = priority_counts.get(s["priority"], 0) + 1

        fig3 = go.Figure(data=[go.Pie(
            labels=list(priority_counts.keys()),
            values=list(priority_counts.values()),
            hole=0.4,
        )])
        fig3.update_layout(title="Priority Breakdown", height=350, margin=dict(l=20, r=20, t=40, b=20))
        html += "<br>" + fig3.to_html(full_html=False, include_plotlyjs="cdn")

        # Add Streamlit embed hint
        html += f"""
        <div style="margin-top:30px; padding:20px; background:#f0f0f0; border-radius:8px; text-align:center;">
            <p style="font-size:14px; color:#666;">
                To view interactive Streamlit dashboard: <code>streamlit run dashboard_embed.py</code>
                <br>Or use the JSON report in <code>report.json</code> for programmatic access.
            </p>
        </div>
        """

        with open(output_path, "w") as f:
            f.write(html)
        return output_path
