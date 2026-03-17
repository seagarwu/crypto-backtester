import os
import tempfile
from pathlib import Path


_mpl_dir = Path(tempfile.gettempdir()) / "crypto-backtester-mpl"
_mpl_dir.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_mpl_dir))
