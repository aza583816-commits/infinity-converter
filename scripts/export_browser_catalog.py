import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.browser_tools import BROWSER_TOOLS
Path(sys.argv[1]).write_text(json.dumps([{'id':t.id,'fields':t.fields} for t in BROWSER_TOOLS]), encoding='utf-8')
