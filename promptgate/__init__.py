__version__ = "0.1.0"

try:
    from .runtime import run_promptgate
except ImportError:
    run_promptgate = None

__all__ = ["__version__", "run_promptgate"]
