"""Root conftest for test discovery configuration."""
import sys
from pathlib import Path

# Ensure src is in the path for imports
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
