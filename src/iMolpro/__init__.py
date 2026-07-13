try:
    from importlib.metadata import version, PackageNotFoundError
except ImportError:  # pragma: no cover - Python < 3.8
    from importlib_metadata import version, PackageNotFoundError

try:
    __version__ = version('iMolpro')
except PackageNotFoundError:  # pragma: no cover - running from an uninstalled checkout
    __version__ = 'unknown'
