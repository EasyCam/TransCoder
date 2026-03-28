"""
TransCoder entry point for python -m transcoder
"""

import sys
from transcoder.cli import main

if __name__ == "__main__":
    sys.exit(main())