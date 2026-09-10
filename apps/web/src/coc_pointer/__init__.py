"""coc-pointer: Clash of Clans clan point score tracker."""

import sys


def main() -> None:
    from coc_pointer.cli import main as cli_main

    sys.exit(cli_main())
