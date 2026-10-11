"""PDF comparison must prove exact glyphs and spaces, without source-assisted repair."""
from scripts.semantic_oracles_office import _logical_text_with_geometric_spaces, _field_present, _logical_pdf_text, _ordered_fields_present


class Page:
    def __init__(self, layout):
        self.layout = layout
    def extract_text(self, **options):
        if options.get('extraction_mode') == 'layout':
            return self.layout
        return 'فحصالسلامةومعداتالوقايةسجل 00050'


def test_layout_recovers_observed_spaces_without_replacing_logical_letters():
    page = Page('00050 لجس ةياقولا تادعمو ةملاسلا صحف')
    assert _logical_text_with_geometric_spaces(page) == 'فحص السلامة ومعدات الوقاية سجل 00050'


def test_missing_printed_word_does_not_get_reconstructed_from_logical_text():
    page = Page('00050 لجس ةياقولا ةملاسلا صحف')
    assert not _field_present('فحص السلامة ومعدات الوقاية سجل 00050', _logical_text_with_geometric_spaces(page))


def test_changed_printed_letter_does_not_get_reconstructed_from_logical_text():
    page = Page('00050 لجس ةياقولا تادعمو ةملاسلا ضحف')
    assert not _field_present('فحص السلامة ومعدات الوقاية سجل 00050', _logical_text_with_geometric_spaces(page))


def test_exact_numeric_fields_do_not_match_longer_identifiers():
    assert not _field_present('Record 00001', 'Record 000012')
    assert _field_present('Record 00001', 'Record\n00001')


def test_wrapped_rtl_pipe_spacing_preserves_complete_fields():
    source = 'فحص السلامة سجل 00000 | 00123 | 00999'
    assert _field_present(source, 'فحص السلامة سجل 00000 | 00123|\n00999')


def test_pipe_spacing_normalization_rejects_missing_or_changed_content():
    source = 'فحص السلامة سجل 00000 | 00123 | 00999'
    for altered in ('فحص سجل 00000 | 00123| 00999',
                    'فحص السلامة سجل 00000 | 00123 00999',
                    'فحص السلامة سجل 00000 | 00999| 00123',
                    'فحص السلامة سجل 00000 | 00123| 009999'):
        assert not _field_present(source, altered)


def test_visual_lam_alef_is_expanded_after_glyph_order_is_restored():
    assert _logical_pdf_text('ﻞﺠﺳ ﺔﻳﺎﻗﻮﻟا تاﺪﻌﻣو ﺔﻣﻼﺴﻟا ﺺﺤﻓ') == 'فحص السلامة ومعدات الوقاية سجل'


def test_reordered_fields_and_reused_duplicate_fields_do_not_pass():
    assert not _ordered_fields_present(['First', 'Second'], 'Second First')
    assert not _ordered_fields_present(['First', 'First'], 'First')
    assert _ordered_fields_present(['First', 'Second'], 'First Second')
