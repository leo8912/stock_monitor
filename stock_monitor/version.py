import os

# Default version if all else fails
__version__ = "0.0.0-dev"

try:
    # 1. Try to get version from installed package metadata (Python 3.8+)
    from importlib import metadata

    try:
        __version__ = metadata.version("stock_monitor")
    except metadata.PackageNotFoundError:
        # Package is not installed
        raise ImportError
except (ImportError, AttributeError):
    # 2. Fallback: Parse pyproject.toml if running from source
    try:
        # Find directory containing pyproject.toml by searching up
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = current_dir

        # Search up to 3 levels up
        for _ in range(3):
            toml_path = os.path.join(project_root, "pyproject.toml")
            if os.path.exists(toml_path):
                with open(toml_path, encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith("version"):
                            parts = line.split("=")
                            if len(parts) == 2:
                                version_str = parts[1].strip().strip('"').strip("'")
                                if version_str:
                                    __version__ = version_str
                                    break
                if __version__ != "0.0.0-dev":
                    break

            parent = os.path.dirname(project_root)
            if parent == project_root:
                break
            project_root = parent
    except Exception:
        pass
