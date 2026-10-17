"""Entry point: python -m kcm.judge "text" --prev "A: ..." (see kcm/cli.py)."""
import sys

from .cli import main

if __name__ == '__main__':
    sys.exit(main())
