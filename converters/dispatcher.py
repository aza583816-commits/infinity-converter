from converters.engine import ConversionEngine


ENGINE = ConversionEngine()

def convert(*, tool, safe_inputs, workspace, timeout, max_pdf_pages, param="", options=None):
    return ENGINE.convert(
        tool=tool,
        safe_inputs=safe_inputs,
        workspace=workspace,
        timeout=timeout,
        max_pdf_pages=max_pdf_pages,
        param=param,
        options=options or {},
    )
