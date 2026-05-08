"""Executive PDF report generator using reportlab."""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class PdfReportGenerator:
    """Generate executive PDF brief from assessment results."""

    ANTI_PATTERN_LABELS = [
        "High-Freq\nPoint Lookups",
        "Agent State\nStorage",
        "App Backend\non Delta",
        "Feature Store\nLatency",
        "High\nConcurrency",
        "Cache Layer\nBypass",
    ]
    ANTI_PATTERN_TYPES = [
        "HIGH_FREQ_POINT_LOOKUP",
        "AGENT_STATE_DELTA_MISUSE",
        "APP_BACKEND_ON_DELTA",
        "FEATURE_STORE_LATENCY",
        "HIGH_CONCURRENCY_COST",
        "CACHING_LAYER_BYPASS",
    ]

    def __init__(
        self,
        scores: dict[str, list[Any]],
        cost_deltas: dict[str, dict[str, Any]],
        buckets: dict[str, list[dict[str, Any]]],
        misuse_findings: dict[str, Any] | None = None,
        readiness_scores: dict[str, Any] | None = None,
    ) -> None:
        self.scores = scores
        self.cost_deltas = cost_deltas
        self.buckets = buckets
        self.misuse_findings = misuse_findings or {}
        self.readiness_scores = readiness_scores or {}

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

        # §17 canonical report sections
        self._build_access_pattern_section(elements, styles)
        self._build_fit_scorecard_section(elements, styles)
        self._build_migration_roadmap_section(elements, styles)

        # Build PDF
        doc.build(elements)
        return output_path

    # ── §17 canonical report sections ──────────────────────────────────────────

    def _build_access_pattern_section(self, elements: list, styles: Any) -> None:
        """§17 Access Pattern Report: anti-pattern heat map + top 5 candidates."""
        from reportlab.lib.colors import HexColor, white, grey
        from reportlab.platypus import Table, TableStyle, Paragraph, Spacer

        elements.append(Paragraph("Access Pattern Report", styles["Heading2"]))

        # Heat map: rows = tables (affected_object), cols = 6 anti-patterns
        affected_objects: dict[str, dict[str, str]] = {}
        for platform, findings_obj in self.misuse_findings.items():
            findings = getattr(findings_obj, "findings", None) or []
            for f in findings:
                obj = str(getattr(f, "affected_object", "unknown"))[:30]
                ftype = str(getattr(f, "finding_type", ""))
                severity = str(getattr(f, "severity", "low"))
                if obj not in affected_objects:
                    affected_objects[obj] = {}
                affected_objects[obj][ftype] = severity

        if affected_objects:
            header = ["Table / Object"] + self.ANTI_PATTERN_LABELS
            heat_data: list[list] = [header]
            for obj, pattern_map in list(affected_objects.items())[:20]:
                row: list = [obj]
                for pt in self.ANTI_PATTERN_TYPES:
                    sev = pattern_map.get(pt, "")
                    if sev == "high":
                        row.append("HIGH")
                    elif sev == "medium":
                        row.append("MED")
                    elif sev == "low":
                        row.append("low")
                    else:
                        row.append("-")
                heat_data.append(row)

            col_w = [100] + [55] * 6
            heat_table = Table(heat_data, colWidths=col_w)
            heat_style = TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1a1a2e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#f8f8f8")]),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ])
            # Colour HIGH/MED cells
            for ri, row in enumerate(heat_data[1:], start=1):
                for ci, cell in enumerate(row[1:], start=1):
                    if cell == "HIGH":
                        heat_style.add("BACKGROUND", (ci, ri), (ci, ri), HexColor("#ff4444"))
                        heat_style.add("TEXTCOLOR", (ci, ri), (ci, ri), white)
                    elif cell == "MED":
                        heat_style.add("BACKGROUND", (ci, ri), (ci, ri), HexColor("#ffaa00"))
            heat_table.setStyle(heat_style)
            elements.append(heat_table)
            elements.append(Spacer(1, 12))

        # Top 5 candidates
        elements.append(Paragraph("Top 5 Migration Candidates", styles["Heading3"]))
        all_scored: list[Any] = []
        for platform_scores in self.scores.values():
            all_scored.extend(platform_scores)
        top5 = sorted(all_scored, key=lambda s: getattr(s, "adjusted_score", 0), reverse=True)[:5]
        for ws in top5:
            ident = str(getattr(ws, "identifier", ""))[:40]
            score = getattr(ws, "adjusted_score", 0)
            bucket = str(getattr(ws, "classification", ""))
            tshirt = str(getattr(ws, "effort_tshirt_size", "M"))
            elements.append(Paragraph(
                f"&bull; <b>{ident}</b> — Score: {score:.1f}, Bucket: {bucket}, Effort: {tshirt}",
                styles["Normal"],
            ))
        elements.append(Spacer(1, 12))

    def _build_fit_scorecard_section(self, elements: list, styles: Any) -> None:
        """§17 Fit Scorecard: traffic-light by table, priority tiers, T-shirt totals."""
        from reportlab.lib.colors import HexColor, white, grey
        from reportlab.platypus import Table, TableStyle, Paragraph, Spacer

        elements.append(Paragraph("Fit Scorecard", styles["Heading2"]))

        all_scores: list[Any] = []
        for platform_scores in self.scores.values():
            all_scores.extend(platform_scores)
        all_scores.sort(key=lambda s: getattr(s, "adjusted_score", 0), reverse=True)

        # Traffic-light table
        sc_data: list[list] = [["Workload", "Bucket", "Priority", "Score", "Effort"]]
        tshirt_counter: dict[str, int] = {}
        for ws in all_scores:
            ident = str(getattr(ws, "identifier", ""))[:35]
            bucket = str(getattr(ws, "classification", ""))
            priority = str(getattr(ws, "priority", "Hold"))
            score = getattr(ws, "adjusted_score", 0)
            tshirt = str(getattr(ws, "effort_tshirt_size", "M"))
            tshirt_counter[tshirt] = tshirt_counter.get(tshirt, 0) + 1
            # Traffic light symbol (text-based)
            light = "P1" if priority == "Priority_1" else ("EVAL" if priority == "Evaluate" else "HOLD")
            sc_data.append([ident, bucket, light, f"{score:.1f}", tshirt])

        if len(sc_data) > 1:
            col_w = [130, 80, 40, 45, 40]
            sc_table = Table(sc_data[:51], colWidths=col_w)  # cap at 50 rows + header
            sc_style = TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1a1a2e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("ALIGN", (2, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#f8f8f8")]),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ])
            for ri, row in enumerate(sc_data[1:], start=1):
                if row[2] == "P1":
                    sc_style.add("BACKGROUND", (2, ri), (2, ri), HexColor("#22aa44"))
                    sc_style.add("TEXTCOLOR", (2, ri), (2, ri), white)
                elif row[2] == "EVAL":
                    sc_style.add("BACKGROUND", (2, ri), (2, ri), HexColor("#ffaa00"))
                else:
                    sc_style.add("BACKGROUND", (2, ri), (2, ri), HexColor("#dd4444"))
                    sc_style.add("TEXTCOLOR", (2, ri), (2, ri), white)
            sc_table.setStyle(sc_style)
            elements.append(sc_table)
            elements.append(Spacer(1, 8))

        # T-shirt summary row
        tshirt_order = ["XS", "S", "M", "L", "XL", "XXL"]
        tshirt_row = "  ".join(f"{s}: {tshirt_counter.get(s, 0)}" for s in tshirt_order)
        elements.append(Paragraph(f"Effort summary — {tshirt_row}", styles["Normal"]))
        elements.append(Spacer(1, 12))

        # Readiness scores
        if self.readiness_scores:
            elements.append(Paragraph("Lakebase Readiness Score", styles["Heading3"]))
            for platform, rs in self.readiness_scores.items():
                total = getattr(rs, "total_score", 0)
                tier = str(getattr(rs, "tier", ""))
                gaps = getattr(rs, "pillar_gaps", [])
                next_step = str(getattr(rs, "recommended_next_step", ""))
                d = getattr(rs, "data_readiness_score", 0)
                s = getattr(rs, "sql_compatibility_score", 0)
                g = getattr(rs, "access_governance_score", 0)
                c = getattr(rs, "cost_business_case_score", 0)
                o = getattr(rs, "org_readiness_score", 0)
                elements.append(Paragraph(
                    f"<b>{platform}</b> — Total: {total}/100 ({tier})",
                    styles["Normal"],
                ))
                elements.append(Paragraph(
                    f"Data:{d}/25  SQL:{s}/25  Gov:{g}/20  Cost:{c}/15  Org:{o}/15",
                    styles["Normal"],
                ))
                if gaps:
                    elements.append(Paragraph(f"Gaps: {', '.join(gaps)}", styles["Normal"]))
                elements.append(Paragraph(f"Next step: {next_step}", styles["Normal"]))
                elements.append(Spacer(1, 6))

    def _build_migration_roadmap_section(self, elements: list, styles: Any) -> None:
        """§17 Migration Roadmap: top 3 architectures + cost savings + 30/60/90 plan."""
        from reportlab.lib.colors import HexColor, white, grey
        from reportlab.platypus import Table, TableStyle, Paragraph, Spacer

        elements.append(Paragraph("Migration Roadmap", styles["Heading2"]))

        # Top 3 architectures
        all_scores: list[Any] = []
        for platform_scores in self.scores.values():
            all_scores.extend(platform_scores)
        all_scores.sort(key=lambda s: getattr(s, "adjusted_score", 0), reverse=True)
        top3 = all_scores[:3]

        elements.append(Paragraph("Top 3 Target Architectures", styles["Heading3"]))
        for i, ws in enumerate(top3, 1):
            ident = str(getattr(ws, "identifier", ""))[:40]
            bucket = str(getattr(ws, "classification", "Analytics"))
            score = getattr(ws, "adjusted_score", 0)
            tshirt = str(getattr(ws, "effort_tshirt_size", "M"))
            recommendation = str(getattr(ws, "recommendation", ""))
            elements.append(Paragraph(
                f"<b>#{i}: {ident}</b> — {bucket} (Score: {score:.1f}, Effort: {tshirt})",
                styles["Normal"],
            ))
            elements.append(Paragraph(recommendation, styles["Normal"]))
            elements.append(Spacer(1, 4))

        # Cost savings table
        elements.append(Paragraph("Cost Savings Projection", styles["Heading3"]))
        cost_data: list[list] = [
            ["Platform", "Current $/mo", "Projected $/mo", "Monthly Savings", "Payback (mo)"]
        ]
        for platform, delta in self.cost_deltas.items():
            current = delta.get("current_estimated_monthly_cost", 0)
            projected = delta.get("projected_lakebase_cost", 0)
            savings = current - projected
            payback = round(projected / max(savings, 1), 1) if savings > 0 else "N/A"
            cost_data.append([
                delta.get("platform", platform),
                f"${current:,.0f}",
                f"${projected:,.0f}",
                f"${savings:,.0f}",
                str(payback),
            ])
        if len(cost_data) > 1:
            cost_table = Table(cost_data, colWidths=[90, 80, 80, 80, 70])
            cost_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1a1a2e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#f8f8f8")]),
            ]))
            elements.append(cost_table)
            elements.append(Spacer(1, 10))

        # 30/60/90 day plan
        elements.append(Paragraph("30/60/90 Day Implementation Plan", styles["Heading3"]))
        p1_names = [
            str(getattr(ws, "identifier", ""))[:30]
            for ws in all_scores if getattr(ws, "priority", "") == "Priority_1"
        ]
        eval_names = [
            str(getattr(ws, "identifier", ""))[:30]
            for ws in all_scores if getattr(ws, "priority", "") == "Evaluate"
        ]
        day30 = ", ".join(p1_names[:3]) or "No Priority 1 workloads"
        day60 = ", ".join(p1_names[3:6]) or "Remaining Priority 1 workloads"
        day90 = ", ".join(eval_names[:3]) or "Evaluate workloads"
        elements.append(Paragraph(f"<b>Days 1-30 (Wave 1):</b> {day30}", styles["Normal"]))
        elements.append(Paragraph(f"<b>Days 31-60 (Wave 1 cont):</b> {day60}", styles["Normal"]))
        elements.append(Paragraph(f"<b>Days 61-90 (Wave 2):</b> {day90}", styles["Normal"]))
        elements.append(Spacer(1, 12))

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
