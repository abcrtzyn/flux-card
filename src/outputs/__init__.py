import importlib
from pathlib import Path

# Automatically discover and import all .py files in this directory
# This triggers the @register_formatter decorators automatically on application startup
current_dir = Path(__file__).parent

for file_path in current_dir.glob("*.py"):
    module_name = file_path.stem
    if module_name != "__init__":
        importlib.import_module(f"outputs.{module_name}")
