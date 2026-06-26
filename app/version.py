from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def package_version() -> str:
    try:
        return version("assurance-workbench-ui")
    except PackageNotFoundError:
        return "0.1.0"


APP_VERSION = package_version()
