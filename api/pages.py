from flask import Blueprint, render_template
from core.tool_registry import list_tools

pages_bp = Blueprint("pages", __name__)

@pages_bp.get("/")
def home():
    return render_template("index.html", tools=list_tools())
