"""Small client-facing catalog for real-page E2E; generated from runtime registry."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.tooling import TOOLS

Path(sys.argv[1]).write_text(
    json.dumps([{"id":tool.id,"input_required":tool.input_required} for tool in TOOLS.values()],ensure_ascii=False),
    encoding="utf-8",
)
