"""STATpy Platform scaffold generator.

Run this script once to create the full folder structure, all __init__.py
files, and requirements.txt. After running, you only need to copy-paste
the actual code files from the GitHub repo into the matching paths.

Usage:
    python scaffold.py

This creates a STATpy_platform/ folder in the current directory.
"""

import os

PACKAGE = "STATpy_platform"

DIRS = [
    "",
    "assets",
    "assets/fonts",
    "assets/js",
    "config",
    "components",
    "shared",
    "data",
    "data/common",
    "data/analytics",
    "data/monitoring",
    "data/saas",
    "features",
    "features/monitoring",
    "features/monitoring/pages",
    "features/monitoring/pages/pd_performance",
    "features/monitoring/pages/lgd_performance",
    "features/monitoring/pages/ead_performance",
    "features/saas",
    "features/saas/pages",
    "features/saas/pages/workspace",
    "source_data",
    "tests",
]

INIT_FILES = {
    "__init__.py": '__version__ = "0.1.0"\n',
    "config/__init__.py": '"""Centralised application configuration."""\n',
    "components/__init__.py": "",
    "shared/__init__.py": '"""Cross-dashboard shared layer."""\n',
    "data/__init__.py": "",
    "data/common/__init__.py": '"""Generic, dashboard-agnostic data helpers."""\n',
    "data/analytics/__init__.py": '"""Shared analytics layer for the STATpy dashboards."""\n',
    "data/monitoring/__init__.py": '"""Monitoring (PD performance) dashboard data layer."""\n',
    "data/saas/__init__.py": '"""SAAS dashboard data layer."""\n',
    "features/__init__.py": "",
    "features/monitoring/__init__.py": "",
    "features/monitoring/pages/__init__.py": "",
    "features/monitoring/pages/pd_performance/__init__.py": "",
    "features/monitoring/pages/lgd_performance/__init__.py": "",
    "features/monitoring/pages/ead_performance/__init__.py": "",
    "features/saas/__init__.py": "",
    "features/saas/pages/__init__.py": "",
    "features/saas/pages/workspace/__init__.py": "",
}

REQUIREMENTS = """\
dash>=2.17
plotly>=5.22
pandas>=2.0
numpy>=1.24
openpyxl>=3.1

# Dev / test
pytest>=8.0
"""


def main():
    if os.path.exists(PACKAGE):
        print(f"ERROR: '{PACKAGE}/' already exists. Remove it first or run from a different directory.")
        return

    for d in DIRS:
        path = os.path.join(PACKAGE, d) if d else PACKAGE
        os.makedirs(path, exist_ok=True)
        print(f"  created  {path}/")

    for filepath, content in INIT_FILES.items():
        full_path = os.path.join(PACKAGE, filepath)
        with open(full_path, "w") as f:
            f.write(content)
        print(f"  wrote    {full_path}")

    req_path = os.path.join(PACKAGE, "requirements.txt")
    with open(req_path, "w") as f:
        f.write(REQUIREMENTS)
    print(f"  wrote    {req_path}")

    print()
    print(f"Scaffold complete. {len(DIRS)} directories and {len(INIT_FILES) + 1} files created.")
    print()
    print("Next steps:")
    print("  1. pip install -r STATpy_platform/requirements.txt")
    print("  2. Copy-paste the code files listed in IMPLEMENTATION_GUIDE_SAAS.md")
    print("  3. Place your dummy_mev_data.xlsx in STATpy_platform/source_data/")
    print("  4. python -m STATpy_platform.app")


if __name__ == "__main__":
    main()
