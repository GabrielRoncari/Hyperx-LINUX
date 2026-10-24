import sys

from .cli import COMMANDS


def main() -> int:
    args = sys.argv[1:]
    if args and (args[0] in COMMANDS or args[0] in ("-h", "--help", "--version")):
        from .cli import main as cli_main
        return cli_main(args)
    from .gui.app import main as gui_main
    return gui_main([sys.argv[0], *args])


if __name__ == "__main__":
    sys.exit(main())
