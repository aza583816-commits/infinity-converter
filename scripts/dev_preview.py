"""Work preview adapter; production continues to use Gunicorn."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app_factory import create_app

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4173)
    parser.add_argument("--strictPort", action="store_true")
    args = parser.parse_args()
    create_app().run(host=args.host, port=args.port, debug=False)
