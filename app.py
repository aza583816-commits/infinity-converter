def word_to_pdf_structured(docx_doc, is_arabic):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm, leftMargin=15 * mm, rightMargin=15 * mm)
    font = pdf_font_name(is_arabic)
    story = []

    # معالجة الفقرات العادية بوضعها داخل خلايا جدول لضمان استقامة الحروف واتجاهها الصحيح
    for par in docx_doc.paragraphs:
        txt = par.text.strip()
        if txt:
            processed_txt = shape_arabic(txt) if is_arabic else txt
            p_style = ParagraphStyle('PStyle', fontName=font, fontSize=11, leading=16, alignment=2 if is_arabic else 0)
            t_cell = Table([[RLParagraph(escape_html(processed_txt), p_style)]], colWidths=[480])
            t_cell.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "RIGHT" if is_arabic else "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(t_cell)
            story.append(Spacer(1, 4))

    for table_elem in docx_doc.tables:
        table_data = []
        for row in table_elem.rows:
            formatted_row = []
            for cell in row.cells:
                cell_text = cell.text.strip()
                processed = shape_arabic(cell_text) if is_arabic else cell_text
                cell_style = ParagraphStyle('TableCell', fontName=font, fontSize=10, leading=14, alignment=2 if is_arabic else 0)
                formatted_row.append(RLParagraph(escape_html(processed), cell_style))
            table_data.append(formatted_row)
            
        if table_data:
            t = Table(table_data, hAlign="CENTER")
            t.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), font),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0ea5e9")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "RIGHT" if is_arabic else "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(Spacer(1, 10))
            story.append(t)
            story.append(Spacer(1, 10))

    doc.build(story)
    return buf.getvalue()
