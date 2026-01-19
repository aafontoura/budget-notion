"""Script to generate sample PDF bank statements for testing."""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from pathlib import Path


def generate_simple_statement():
    """Generate a simple bank statement PDF."""
    output_path = Path(__file__).parent / "pdfs" / "simple_statement.pdf"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(str(output_path), pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    title = Paragraph("<b>Bank Statement</b>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 1 * cm))

    # Account info
    info = Paragraph("<b>Account:</b> NL01BANK0123456789<br/><b>Period:</b> January 2025", styles['Normal'])
    elements.append(info)
    elements.append(Spacer(1, 0.5 * cm))

    # Transaction table
    data = [
        ['Date', 'Description', 'Amount'],
        ['2025-01-19', 'Albert Heijn Supermarket', '-€50.00'],
        ['2025-01-18', 'Shell Gas Station', '-€60.00'],
        ['2025-01-17', 'Restaurant De Eethoek', '-€35.50'],
        ['2025-01-16', 'Salary Deposit', '€2,500.00'],
        ['2025-01-15', 'ABN AMRO Car Insurance', '-€52.15'],
    ]

    table = Table(data, colWidths=[3 * cm, 10 * cm, 3 * cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))

    elements.append(table)

    # Build PDF
    doc.build(elements)
    print(f"Generated: {output_path}")


def generate_dutch_statement():
    """Generate a Dutch bank statement PDF (ABN AMRO style)."""
    output_path = Path(__file__).parent / "pdfs" / "abn_amro_statement.pdf"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(str(output_path), pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    title = Paragraph("<b>ABN AMRO - Rekeningoverzicht</b>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 1 * cm))

    # Account info
    info = Paragraph(
        "<b>Rekeningnummer:</b> NL01ABNA0123456789<br/>"
        "<b>Periode:</b> 01-01-2025 tot 19-01-2025<br/>"
        "<b>Naam:</b> J. de Vries",
        styles['Normal']
    )
    elements.append(info)
    elements.append(Spacer(1, 0.5 * cm))

    # Transaction table (Dutch headers)
    data = [
        ['Datum', 'Omschrijving', 'Bedrag'],
        ['19-01-2025', 'Albert Heijn AH 1234', '-€ 45,50'],
        ['18-01-2025', 'Shell Tankstation', '-€ 65,00'],
        ['17-01-2025', 'Jumbo Supermarkt', '-€ 38,75'],
        ['16-01-2025', 'Salaris Werkgever BV', '€ 2.500,00'],
        ['15-01-2025', 'NS Reizen - OV Chipkaart', '-€ 50,00'],
        ['14-01-2025', 'Bol.com Aankoop', '-€ 29,99'],
        ['13-01-2025', 'IKEA Meubels', '-€ 250,00'],
    ]

    table = Table(data, colWidths=[3 * cm, 10 * cm, 3 * cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00A86B')),  # ABN green
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))

    elements.append(table)

    # Build PDF
    doc.build(elements)
    print(f"Generated: {output_path}")


def generate_mixed_format_statement():
    """Generate a statement with mixed date/amount formats for testing."""
    output_path = Path(__file__).parent / "pdfs" / "mixed_format_statement.pdf"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(str(output_path), pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    title = Paragraph("<b>International Bank Statement</b>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 1 * cm))

    # Transaction table with various formats
    data = [
        ['Date', 'Description', 'Amount'],
        ['2025-01-19', 'Grocery Store', '-$50.00'],  # US format
        ['19/01/2025', 'Gas Station', '-€60,00'],  # European format
        ['19 Jan 2025', 'Restaurant', '($35.50)'],  # Parentheses for negative
        ['2025-01-16', 'Salary', '$2,500.00'],  # US format with comma
        ['16-01-2025', 'Insurance', '-R$ 52,15'],  # Brazilian format
    ]

    table = Table(data, colWidths=[3 * cm, 10 * cm, 3 * cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.navy),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))

    elements.append(table)

    # Build PDF
    doc.build(elements)
    print(f"Generated: {output_path}")


if __name__ == "__main__":
    print("Generating sample PDF bank statements...")
    try:
        generate_simple_statement()
        generate_dutch_statement()
        generate_mixed_format_statement()
        print("\nAll sample PDFs generated successfully!")
        print("Location: tests/fixtures/pdfs/")
    except Exception as e:
        print(f"Error generating PDFs: {e}")
        print("\nNote: You need to install reportlab:")
        print("  pip install reportlab")
