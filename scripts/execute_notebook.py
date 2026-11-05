"""Execute every notebook cell in this Python environment, with real MySQL output."""
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from jupyter_client import AsyncKernelManager
from jupyter_client.kernelspec import KernelSpecManager

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "notebooks" / "Little_Lemon_Database.ipynb"
nb = nbformat.read(path, as_version=4)
# Clear prior output so a failed run cannot masquerade as the previous success.
for cell in nb.cells:
    if cell.cell_type == "code":
        cell.outputs = []
        cell.execution_count = None
with tempfile.TemporaryDirectory(prefix="little-lemon-kernel-") as directory:
    kernel = Path(directory) / "python3"
    kernel.mkdir()
    (kernel / "kernel.json").write_text(json.dumps({
        "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
        "display_name": "Little Lemon database Python", "language": "python",
    }))
    manager = AsyncKernelManager(kernel_name="python3", kernel_spec_manager=KernelSpecManager(kernel_dirs=[directory]))
    client = NotebookClient(nb, km=manager, timeout=180, allow_errors=False,
                            resources={"metadata": {"path": str(ROOT)}})
    # We supplied the manager, so explicitly request kernel/channel cleanup.
    client.execute(cleanup_kc=True)
errors = [output for cell in nb.cells if cell.cell_type == "code" for output in cell.outputs if output.output_type == "error"]
assert not errors
nbformat.validate(nb)
nbformat.write(nb, path)
summary = {
    "executed_at_utc": datetime.now(timezone.utc).isoformat(),
    "code_cells": sum(cell.cell_type == "code" for cell in nb.cells),
    "executed_code_cells": sum(cell.cell_type == "code" and cell.execution_count is not None for cell in nb.cells),
    "unexpected_errors": len(errors), "kernel_python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
}
(ROOT / "evidence").mkdir(exist_ok=True)
(ROOT / "evidence" / "notebook_execution.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
