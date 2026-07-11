import sys
from pathlib import Path

# backend/ 를 import 경로에 추가 (pyproject pythonpath 보완)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
