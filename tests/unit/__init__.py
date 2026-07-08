import os
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
src_root = repo_root / 'src'
for path in (str(repo_root), str(src_root)):
    if path not in sys.path:
        sys.path.insert(0, path)
