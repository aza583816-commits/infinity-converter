"""Source-to-output regression: ambiguous headers must never silently lose cells."""
import csv
import json

import pytest
from openpyxl import Workbook

from converters.office_advanced import csv_to_json, xlsx_to_json


@pytest.mark.parametrize("header", [
    "name,name\nfirst,second\n",
    "name,\nfirst,second\n",
    " name , name \nfirst,second\n",
])
def test_csv_to_json_rejects_headers_that_would_drop_data(tmp_path, header):
    source, output = tmp_path / "ambiguous.csv", tmp_path / "result.json"
    source.write_text(header, encoding="utf-8")
    with pytest.raises(ValueError, match="أعمدة"):
        csv_to_json(source, output)
    assert not output.exists()


def test_xlsx_to_json_rejects_duplicate_headers_per_sheet(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Grade", "Grade"])
    sheet.append([80, 95])
    source, output = tmp_path / "ambiguous.xlsx", tmp_path / "result.json"
    workbook.save(source)
    with pytest.raises(ValueError, match="مكررة"):
        xlsx_to_json(source, output)
    assert not output.exists()


def test_xlsx_to_json_auto_names_blank_header_without_collisions(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Name", None])
    sheet.append(["Test", 23])
    source, output = tmp_path / "named.xlsx", tmp_path / "result.json"
    workbook.save(source)
    xlsx_to_json(source, output)
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result[sheet.title] == [{"Name": "Test", "column_2": 23}]
