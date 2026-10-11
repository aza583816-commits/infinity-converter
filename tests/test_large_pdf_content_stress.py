"""Long bilingual PDFs: complete text, images, geometry and page order."""
import hashlib

import pymupdf

from converters.pdf import extract_pdf_pages,merge_pdfs,compress_pdf
from converters.pdf_advanced import reorder_pages,rotate_selected


def test_120_page_bilingual_pdf_pipeline_preserves_every_record_and_visual(tmp_path):
    source=tmp_path/'source.pdf';reference=[];visuals={}
    with pymupdf.open() as doc:
        for i in range(120):
            width,height=(842,595) if i%2 else (595,842)
            page=doc.new_page(width=width,height=height)
            page.insert_text((35,35),f'PAGE {i+1:04d} / CODE 00123 / END 00999',fontsize=15)
            rows=''.join(f'<tr><td>R{i:03d}{j:02d}X</td><td>معدات السلامة Safety equipment</td><td>{i*20+j}.25</td></tr>' for j in range(20))
            spare=page.insert_htmlbox(pymupdf.Rect(35,65,width-35,height-45),
                '<style>table{font-size:10px;width:100%;border-collapse:collapse}td{border:1px solid #165c7a;padding:2px}</style><table>'+rows+'</table>')[0]
            assert spare>=0,'Source fixture must fit before conversion'
            page.draw_rect(pymupdf.Rect(width-70,8,width-35,28),color=(0,.5,.7),fill=(0,.5,.7))
            reference.append(page.get_text())
            if i%17==0:visuals[i]=hashlib.sha256(page.get_pixmap().samples).hexdigest()
        doc.subset_fonts();doc.save(source,garbage=4,deflate=True)
    before=source.read_bytes()
    odd=tmp_path/'odd.pdf';even=tmp_path/'even.pdf';merged=tmp_path/'merged.pdf';ordered=tmp_path/'ordered.pdf'
    extract_pdf_pages(source,odd,','.join(str(i) for i in range(1,121,2)))
    extract_pdf_pages(source,even,','.join(str(i) for i in range(2,121,2)))
    merge_pdfs([odd,even],merged)
    order=[n for i in range(1,61) for n in (i,i+60)]
    reorder_pages(merged,ordered,','.join(map(str,order)))
    compressed=tmp_path/'compressed.pdf';compress_pdf(ordered,compressed)
    rotated=tmp_path/'rotated.pdf';rotate_selected(compressed,rotated,'1,60,120',90)
    for path in (ordered,compressed,rotated):
        with pymupdf.open(path) as pdf:
            assert len(pdf)==120
            for i,page in enumerate(pdf):
                assert page.get_text()==reference[i],(path.name,i)
                expected_rotation=90 if path==rotated and i in (0,59,119) else 0
                assert page.rotation==expected_rotation
                if i in visuals and not expected_rotation:
                    assert hashlib.sha256(page.get_pixmap().samples).hexdigest()==visuals[i],(path.name,i)
    assert source.read_bytes()==before
