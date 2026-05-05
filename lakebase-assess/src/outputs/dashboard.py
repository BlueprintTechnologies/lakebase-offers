"""Dashboard HTML generator placeholder -- see pdf_report.generate_dashboard for Plotly output."""

# This module exists as a separate entry point for standalone dashboard generation.
# The primary Plotly dashboard output is in pdf_report.py.


def generate_dashboard_html(scores, cost_deltas, buckets, output_path):
    """Alias for PdfReportGenerator.generate_dashboard for backward compatibility."""
    from src.outputs.pdf_report import PdfReportGenerator
    gen = PdfReportGenerator(scores, cost_deltas, buckets)
    return gen.generate_dashboard(output_path)
