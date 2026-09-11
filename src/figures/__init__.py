"""每个 fig 模块只生成一幅论文图。"""
import os
from pathlib import Path
os.environ.setdefault("MPLCONFIGDIR", str(Path("outputs/.matplotlib").resolve()))
