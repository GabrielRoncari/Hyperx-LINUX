import sys

from .cli import COMMANDS


def main() -> int:
    args = sys.argv[1:]
    if args and (args[0] in COMMANDS or args[0] in ("-h", "--help", "--version")):
        from .cli import main as cli_main
        return cli_main(args)
    try:
        from .gui.app import main as gui_main
    except (ImportError, ValueError) as e:  # ValueError: gi has no GTK 4 / libadwaita typelib
        print(f"The window needs PyGObject, GTK 4 and libadwaita ({e}).\n"
              "The command line works without them: hyperx-linux -h", file=sys.stderr)
        return 1
    return gui_main([sys.argv[0], *args])


if __name__ == "__main__":
    sys.exit(main())
