import sys

from .cli import main

if __name__ == "__main__":  # guard: PDF-reading worker processes import this module too
    sys.exit(main())
