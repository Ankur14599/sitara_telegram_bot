import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

class InvoiceService:
    @staticmethod
    def generate_invoice_pdf(business: dict, order: dict) -> bytes:
        """Generate a PDF invoice in memory and return as bytes."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # Header
        business_name = business.get("business_name", "Small Business")
        elements.append(Paragraph(f"<b>{business_name}</b>", styles["Title"]))
        elements.append(Paragraph("Invoice", styles["Heading2"]))
        elements.append(Spacer(1, 12))

        # Order Details
        elements.append(Paragraph(f"<b>Order Number:</b> {order.get('order_number')}", styles["Normal"]))
        elements.append(Paragraph(f"<b>Date:</b> {datetime.utcnow().strftime('%Y-%m-%d')}", styles["Normal"]))
        elements.append(Paragraph(f"<b>Customer:</b> {order.get('customer_name')}", styles["Normal"]))
        elements.append(Spacer(1, 12))

        # Items Table
        currency = business.get("currency_symbol", "₹")
        data = [["Item", "Quantity", "Price", "Total"]]
        
        for item in order.get("items", []):
            qty = item.get("quantity", 1)
            price = item.get("unit_price", 0)
            total = item.get("total_price", qty * price)
            data.append([item.get("name"), str(qty), f"{currency}{price}", f"{currency}{total}"])

        # Totals
        data.append(["", "", "Subtotal:", f"{currency}{order.get('subtotal', 0)}"])
        if order.get("discount", 0) > 0:
            data.append(["", "", "Discount:", f"-{currency}{order.get('discount')}"])
        data.append(["", "", "Total Amount:", f"<b>{currency}{order.get('total_amount', 0)}</b>"])
        
        paid = order.get("amount_paid", 0)
        data.append(["", "", "Amount Paid:", f"{currency}{paid}"])
        data.append(["", "", "Balance Due:", f"<b>{currency}{order.get('total_amount', 0) - paid}</b>"])

        t = Table(data, colWidths=[200, 100, 100, 100])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(t)
        
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

invoice_service = InvoiceService()
