"""`python -m urltitle` 入口。"""

import sys

try:
    from .urltitle import main
except ImportError:  # 直接在项目目录里运行：python __main__.py
    from urltitle import main

if __name__ == "__main__":
    sys.exit(main())
