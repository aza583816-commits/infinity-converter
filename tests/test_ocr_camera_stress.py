"""Synthetic camera receipts: skew, compression and EXIF display orientation."""
import json
import re
import unicodedata

import pytest
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from converters.ocr import ocr_image
from converters.mega_tools import ocr_receipt_fields


def camera_receipt(path, language, profile):
    canvas = Image.new('RGB', (1800, 1200), '#e1ded4')
    pen = ImageDraw.Draw(canvas)
    english = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 52)
    arabic = ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf', 58)
    headings={'english':['SAFETY EQUIPMENT RECEIPT'], 'arabic':['فاتورة معدات السلامة'],
              'mixed':['Safety equipment','فاتورة معدات السلامة']}[language]
    for i,line in enumerate(headings):
        pen.text((80+i*850,65),line,font=arabic if re.search('[\u0600-\u06ff]',line) else english,fill='#555555')
    for i,line in enumerate(('Email test@example.com','Date 26/09/2026','Phone +966501234567',
                             'Total SAR 1250.50','Item 00123 Qty 02 Unit 625.25')):
        pen.text((90,260+i*145),line,font=english,fill='#555555')
    if profile=='skew':
        transformed=canvas.rotate(2.5,resample=Image.Resampling.BICUBIC,expand=True,fillcolor='#e1ded4')
        canvas.close();canvas=transformed.filter(ImageFilter.GaussianBlur(.65));transformed.close()
        canvas.save(path,quality=45)
    else:
        # Stored pixels are landscape-rotated; camera EXIF says to display upright.
        rotated=canvas.transpose(Image.Transpose.ROTATE_90)
        exif=Image.Exif();exif[274]=6
        rotated.save(path,quality=70,exif=exif);rotated.close()
    canvas.close()
    return headings


@pytest.mark.parametrize('language',('english','arabic','mixed'))
@pytest.mark.parametrize('profile',('skew','exif'))
def test_camera_receipt_exact_fields_and_bilingual_words(tmp_path,language,profile):
    source=tmp_path/'camera.jpg';headings=camera_receipt(source,language,profile)
    before=source.read_bytes();fields_path=tmp_path/'fields.json';text_path=tmp_path/'plain.txt'
    ocr_receipt_fields(source,fields_path,'ara+eng')
    fields=json.loads(fields_path.read_text())
    assert fields['emails']==['test@example.com'],fields
    assert '26/09/2026' in fields['dates'],fields
    assert 'SAR 1250.50' in fields['money'],fields
    assert '966501234567' in [re.sub(r'\D','',p) for p in fields['phones']],fields
    ocr_image(source,text_path,lang='ar+en')
    text=unicodedata.normalize('NFKC',text_path.read_text()).casefold()
    for line in headings:
        for word in line.casefold().split():assert word in text,(word,text)
    for value in ('test@example.com','26/09/2026','1250.50','00123','625.25'):
        assert value in text,(value,text)
    phone=next(line for line in text.splitlines() if line.startswith('phone'))
    assert re.sub(r'\D','',phone)=='966501234567',text
    assert source.read_bytes()==before


def test_exif_searchable_pdf_and_json_preserve_display_geometry_and_text(tmp_path):
    import pymupdf
    from PIL import ImageOps
    from converters.ocr_advanced import image_to_searchable_pdf,image_ocr_json,ocr_emails,ocr_tables_csv
    source=tmp_path/'camera.jpg';camera_receipt(source,'mixed','exif')
    before=source.read_bytes()
    searchable=tmp_path/'searchable.pdf';structured=tmp_path/'ocr.json'
    image_to_searchable_pdf(source,searchable,'ar+en');image_ocr_json(source,structured,'ar+en')
    fields=json.loads(structured.read_text())
    for word in ('Safety','معدات','السلامة','test@example.com','26/09/2026','1250.50'):
        assert word.casefold() in unicodedata.normalize('NFKC',fields['text']).casefold(),fields
    with Image.open(source) as stored,ImageOps.exif_transpose(stored) as displayed:
        width,height=displayed.size
        for box in fields['words']:
            assert 0<=box['left']<box['left']+box['width']<=width
            assert 0<=box['top']<box['top']+box['height']<=height
        with pymupdf.open(searchable) as pdf:
            assert len(pdf)==1 and pdf[0].rect.width>pdf[0].rect.height
            for word in ('Safety','معدات','السلامة','test@example.com','26/09/2026','1250.50'):
                assert word.casefold() in unicodedata.normalize('NFKC',pdf[0].get_text()).casefold()
            embedded=pdf.extract_image(pdf[0].get_images()[0][0])
            from io import BytesIO
            with Image.open(BytesIO(embedded['image'])) as decoded:
                assert decoded.size==displayed.size
                assert decoded.convert('RGB').tobytes()==displayed.convert('RGB').tobytes()
    emails=tmp_path/'emails.txt';table=tmp_path/'table.csv'
    ocr_emails(source,emails,'ar+en');ocr_tables_csv(source,table,'ar+en')
    assert 'test@example.com' in emails.read_text()
    for value in ('test@example.com','26/09/2026','1250.50'):assert value in table.read_text()
    assert source.read_bytes()==before


@pytest.mark.parametrize('orientation',range(1,9))
def test_camera_decoder_respects_all_declared_orientations_without_rewriting_source(tmp_path,orientation):
    from PIL import ImageOps
    from converters.ocr import _load_display_image
    source=tmp_path/'pixels.png';canvas=Image.new('RGB',(31,19),'white')
    ImageDraw.Draw(canvas).rectangle((0,0,9,7),fill='red')
    exif=Image.Exif();exif[274]=orientation;canvas.save(source,exif=exif);canvas.close()
    before=source.read_bytes()
    with Image.open(source) as stored,ImageOps.exif_transpose(stored) as expected,_load_display_image(source) as actual:
        assert actual.size==expected.size and actual.tobytes()==expected.convert('RGB').tobytes()
        assert actual.getexif().get(274) is None
    assert source.read_bytes()==before


def test_twelve_page_scanned_bilingual_pdf_keeps_all_page_records_in_order(tmp_path):
    import pymupdf
    from io import BytesIO
    from converters.ocr import ocr_pdf
    source=tmp_path/'scanned.pdf';output=tmp_path/'scan.txt'
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',52)
    arabic=ImageFont.truetype('/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',58)
    records=[]
    with pymupdf.open() as pdf:
        for i in range(1,13):
            image=Image.new('RGB',(1800,1200),'#f5f2ea');pen=ImageDraw.Draw(image)
            lines=[f'PAGE {i:03d} SAFETY INSPECTION',f'RECORD {i:05d} CODE 00123',f'AMOUNT {i*100}.50 SAR']
            for j,line in enumerate(lines):pen.text((100,200+j*180),line,font=font,fill='#353535')
            pen.text((100,800),'فحص معدات السلامة',font=arabic,fill='#353535')
            rotated=image.rotate(1.4,resample=Image.Resampling.BICUBIC,expand=True,fillcolor='#f5f2ea')
            data=BytesIO();rotated.save(data,format='JPEG',quality=60);rotated.close();image.close()
            page=pdf.new_page(width=864,height=600);page.insert_image(page.rect,stream=data.getvalue())
            assert not page.get_text(),'Fixture must require actual OCR'
            records.append(lines)
        pdf.save(source)
    before=source.read_bytes();ocr_pdf(source,output,'ar+en',max_pages=12,dpi=200)
    text=unicodedata.normalize('NFKC',output.read_text())
    for i,lines in enumerate(records,1):
        marker=f'--- صفحة {i} ---'
        chunk=text.split(marker,1)[1].split('--- صفحة ',1)[0]
        for line in lines:assert line in chunk,(i,line,chunk)
        for word in ('فحص','معدات','السلامة'):assert word in chunk,(i,word,chunk)
    assert [text.index(f'--- صفحة {i} ---') for i in range(1,13)]==sorted(text.index(f'--- صفحة {i} ---') for i in range(1,13))
    assert source.read_bytes()==before
