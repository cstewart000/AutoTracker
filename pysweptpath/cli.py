"""CLI: config.xml support and overrides. See PDR §2."""

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .analysis import run_analysis

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def run(
    config_path: str, dxf_out: str | None = None, animation: bool | None = None
) -> int:
    """CLI entry: run analysis from config.xml. Returns process exit code."""
    try:
        result = run_analysis(
            config_path, dxf_out=dxf_out, animation=animation, write_files=True
        )
        return 0 if result.ok else 1
    except Exception as e:
        logger.exception("Analysis failed: %s", e)
        return 1


def main() -> int:
    p = argparse.ArgumentParser(
        description="pySweptPath – Ackermann swept path simulator"
    )
    p.add_argument("--config", "-c", default="config.xml", help="Project config.xml")
    p.add_argument("--dxf-out", help="Output DXF path (overrides config)")
    p.add_argument(
        "--animation",
        action="store_true",
        help="Generate animation GIF (overrides config)",
    )
    p.add_argument(
        "--no-animation",
        action="store_true",
        help="Skip animation (overrides config)",
    )
    p.add_argument("--version", action="version", version=__version__)
    args = p.parse_args()
    if not Path(args.config).exists():
        logger.error("Config not found: %s", args.config)
        return 1
    anim_override = (
        True if args.animation else (False if args.no_animation else None)
    )
    return run(args.config, dxf_out=args.dxf_out, animation=anim_override)


if __name__ == "__main__":
    sys.exit(main())
