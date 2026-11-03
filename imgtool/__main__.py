"""支持 python -m imgtool 的方式运行。"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
