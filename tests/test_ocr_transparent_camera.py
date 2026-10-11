"""Transparency must not turn visible black lettering into black-on-black OCR."""
from PIL import Image,ImageDraw,ImageFont
from converters.ocr import ocr_image


def test_transparent_black_camera_letters_are_read_against_display_background(tmp_path):
    source=tmp_path/'transparent.png';output=tmp_path/'text.txt'
    image=Image.new('RGBA',(1700,380),(0,0,0,0))
    draw=ImageDraw.Draw(image);font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',66)
    draw.text((70,45),'SAFETY REPORT 00123',font=font,fill=(0,0,0,255))
    draw.text((70,160),'AMOUNT 1250.50 SAR',font=font,fill=(0,0,0,255))
    image.save(source);image.close();before=source.read_bytes()
    ocr_image(source,output,'en')
    text=output.read_text()
    assert 'SAFETY REPORT 00123' in text and 'AMOUNT 1250.50 SAR' in text,text
    assert source.read_bytes()==before
