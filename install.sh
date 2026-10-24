#!/usr/bin/env bash
# Install HyperX Linux for the current user (no root except for the udev rules).
#
#   ./install.sh                  install, start in the tray at login
#   ./install.sh --no-autostart   install without the login entry
#   ./install.sh --uninstall      remove everything this script installed
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
APP_ID="io.github.gabrielroncari.HyperXLinux"
BIN="$HOME/.local/bin/hyperx-linux"
APPS="$HOME/.local/share/applications"
AUTOSTART="$HOME/.config/autostart"
RULE=/etc/udev/rules.d/70-hyperx-linux.rules

autostart=1
case "${1:-}" in
    --no-autostart) autostart=0 ;;
    --uninstall)
        rm -f "$BIN" "$APPS/$APP_ID.desktop" "$AUTOSTART/$APP_ID.desktop"
        if [ -e "$RULE" ]; then
            echo "Removing udev rules (sudo)…"
            sudo rm -f "$RULE" && sudo udevadm control --reload-rules
        fi
        echo "Uninstalled. Settings are kept in ~/.config/hyperx-linux."
        exit 0 ;;
    "") ;;
    *) echo "usage: $0 [--no-autostart | --uninstall]" >&2; exit 2 ;;
esac

if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
    echo "Python 3.10 or newer is required." >&2; exit 1
fi
if ! python3 -c 'import gi; gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")' 2>/dev/null; then
    echo "Note: GTK 4 / libadwaita bindings not found; only the command line will work."
    echo "      Debian/Ubuntu: sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1"
    echo "      Fedora: sudo dnf install python3-gobject gtk4 libadwaita   Arch: sudo pacman -S python-gobject gtk4 libadwaita"
fi

# udev rules, generated from the drivers so they always match the supported devices
rules="$(PYTHONPATH="$SRC" python3 -m hyperx_linux udev-rules)"
if [ "$(cat "$RULE" 2>/dev/null)" != "$rules" ]; then
    echo "Installing udev rules (sudo)…"
    printf '%s\n' "$rules" | sudo tee "$RULE" >/dev/null
    sudo udevadm control --reload-rules
    sudo udevadm trigger --subsystem-match=hidraw --action=change
fi

mkdir -p "$(dirname "$BIN")" "$APPS" "$AUTOSTART"
cat > "$BIN" <<EOF
#!/bin/sh
PYTHONPATH="$SRC\${PYTHONPATH:+:\$PYTHONPATH}" exec python3 -m hyperx_linux "\$@"
EOF
chmod +x "$BIN"

desktop() { sed -e "s|@BIN@|$BIN|" -e "s|@ARGS@|$1|" -e 's| $||' "$SRC/data/hyperx-linux.desktop.in"; }
desktop "" > "$APPS/$APP_ID.desktop"
if [ "$autostart" = 1 ]; then
    desktop "--background" > "$AUTOSTART/$APP_ID.desktop"
else
    rm -f "$AUTOSTART/$APP_ID.desktop"
fi

echo "Done. Run 'hyperx-linux' (window) or 'hyperx-linux status' (terminal)."
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "Add ~/.local/bin to your PATH to use the command." ;; esac
