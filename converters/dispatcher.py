from converters.engine import ConversionEngine


ENGINE = ConversionEngine()

def convert(*, tool, safe_inputs, workspace, timeout, max_pdf_pages):
    result = ENGINE.convert(
        tool=tool,
        safe_inputs=safe_inputs,
        workspace=workspace,
        timeout=timeout,
        max_pdf_pages=max_pdf_pages,
    )
    return result.path, result.name, result.mime
