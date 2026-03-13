#!/usr/bin/env python3
import sys
import traceback
from vdx.cli import main

if __name__ == "__main__":
    try:
        main()
    except BaseException as e:
        with open(".vdx_error.log", "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        raise
