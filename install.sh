#!/bin/sh
# Install HyperX Linux for the current user, dependencies included. POSIX sh (bash, dash, BusyBox).
#
#   From a clone:     ./install.sh [options]
#   Without cloning:  curl -fsSL https://raw.githubusercontent.com/GabrielRoncari/Hyperx-LINUX/main/install.sh | sh
#                     (options go after "sh -s --", e.g. "| sh -s -- --no-autostart")
#
#   --no-autostart   don't start in the tray at login
#   --no-deps        don't install Python, PyGObject, GTK 4 and libadwaita with the package manager
#   --rules-only     only install the udev rules (e.g. for the Flatpak)
#   --uninstall      remove everything this script installed
#
# Root is needed for the packages and the udev rules: sudo, doas or run0, whichever exists.
# Everything runs from main() at the end, so a piped script is read completely before it starts.
set -eu

REPO="https://github.com/GabrielRoncari/Hyperx-LINUX"
TARBALL="${HYPERX_LINUX_TARBALL:-$REPO/archive/refs/heads/main.tar.gz}"
APP_ID="io.github.gabrielroncari.HyperXLinux"
BIN="$HOME/.local/bin/hyperx-linux"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
DOWNLOADED="$DATA/hyperx-linux/app"
APPS="$DATA/applications"
ICON="$DATA/icons/hicolor/scalable/apps/$APP_ID.svg"
AUTOSTART="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
RULE=/etc/udev/rules.d/70-hyperx-linux.rules
GROUP=hyperx
ME=$(id -un)
SRC=$(cd "$(dirname "$0")" && pwd)

say() { printf '%s\n' "$*"; }

as_root() {
    if [ "$(id -u)" = 0 ]; then "$@"
    elif command -v sudo >/dev/null 2>&1; then sudo "$@"
    elif command -v doas >/dev/null 2>&1; then doas "$@"
    elif command -v run0 >/dev/null 2>&1; then run0 "$@"
    else say "Need root for: $*  (install sudo or doas, or run this as root)"; return 1
    fi
}

# Use the clone this script lives in; when piped from curl there is none, so download the latest
# version and hand over to the install.sh inside it, which always matches the code it installs
fetch_source() {
    [ -f "$SRC/hyperx_linux/__init__.py" ] && return 0
    say "Downloading HyperX Linux…"
    tmp=$(mktemp -d)
    if command -v curl >/dev/null 2>&1; then curl -fsSL "$TARBALL" -o "$tmp/src.tar.gz"
    elif command -v wget >/dev/null 2>&1; then wget -qO "$tmp/src.tar.gz" "$TARBALL"
    else say "curl or wget is needed to download HyperX Linux."; exit 1
    fi
    tar -xzo -f "$tmp/src.tar.gz" -C "$tmp"   # -o: files belong to whoever installs
    for dir in "$tmp"/*/; do   # old BusyBox also extracts GitHub's pax_global_header as a file
        [ -f "${dir}hyperx_linux/__init__.py" ] && break
    done
    [ -f "${dir}hyperx_linux/__init__.py" ] || { say "The download doesn't contain HyperX Linux: $TARBALL"; exit 1; }
    rm -rf "$DOWNLOADED"
    mkdir -p "$(dirname "$DOWNLOADED")"
    mv "${dir%/}" "$DOWNLOADED"
    rm -rf "$tmp"
    exec sh "$DOWNLOADED/install.sh" "$@"
}

python_ok() { python3 -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; }
# a real import: the typelibs GTK depends on (cairo, Pango…) may be missing even when Gtk's is there,
# and so may PyGObject's cairo support (python3-gi-cairo), which the drawings need
gui_ok() {
    python3 -c 'import gi; gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1"); from gi.repository import Gtk, Adw; gi.require_foreign("cairo")' \
        >/dev/null 2>&1
}

# Package-manager command for Python 3, PyGObject, pycairo, GTK 4 and libadwaita (empty: not automated)
deps_cmd() {
    if command -v apt-get >/dev/null 2>&1; then
        echo "apt-get install -y python3 python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1"
    elif command -v dnf >/dev/null 2>&1; then
        # gobject-introspection has cairo's typelib, which minimal installs lack
        echo "dnf install -y python3 python3-gobject python3-cairo gobject-introspection gtk4 libadwaita"
    elif command -v zypper >/dev/null 2>&1; then
        # openSUSE names Python modules after the interpreter: python313-gobject…
        v=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])' 2>/dev/null || echo 3)
        echo "zypper --non-interactive install python3 python$v-gobject python$v-gobject-cairo typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1"
    elif command -v pacman >/dev/null 2>&1; then
        echo "pacman -S --needed --noconfirm python python-gobject python-cairo gtk4 libadwaita"
    elif command -v xbps-install >/dev/null 2>&1; then
        echo "xbps-install -Sy python3 python3-gobject python3-cairo gtk4 libadwaita"
    elif command -v apk >/dev/null 2>&1; then
        echo "apk add python3 py3-gobject3 py3-cairo gtk4.0 libadwaita"
    elif command -v eopkg >/dev/null 2>&1; then
        echo "eopkg install -y python3 python-gobject python-cairo libgtk-4 libadwaita"
    fi
}

deps_hint() {
    cmd=$(deps_cmd)
    if [ -n "$cmd" ]; then say "  sudo $cmd"
    elif command -v emerge >/dev/null 2>&1; then say "  emerge dev-python/pygobject dev-python/pycairo gui-libs/gtk gui-libs/libadwaita"
    elif [ -e /etc/NIXOS ]; then say "  add python3Packages.pygobject3, gtk4 and libadwaita to your configuration"
    else say "  install PyGObject (python3-gi), pycairo, GTK 4 and libadwaita from your distribution"
    fi
}

# shellcheck disable=SC2086  # $cmd is a list of words on purpose
install_deps() {
    if python_ok && gui_ok; then return 0; fi
    cmd=$(deps_cmd)
    if [ -z "$cmd" ]; then
        say "Install these with your package manager, then run this again:"; deps_hint; return 0
    fi
    say "Installing dependencies: $cmd"
    if ! as_root $cmd </dev/null; then
        case "$cmd" in   # a fresh system may not have downloaded the package lists yet
            apt-get*) as_root apt-get update </dev/null && as_root $cmd </dev/null || true ;;
        esac
    fi
}

# TAG+="uaccess" needs a seat manager (logind, or elogind on eudev systems) and the rule that turns
# the tag into permissions (73-seat-late.rules, from systemd or elogind); otherwise use a group
uaccess_works() {
    [ -d /run/systemd/seats ] || return 1
    for f in /etc/udev/rules.d/73-seat-late.rules /usr/lib/udev/rules.d/73-seat-late.rules \
             /lib/udev/rules.d/73-seat-late.rules; do
        if grep -q uaccess "$f" 2>/dev/null; then return 0; fi
    done
    return 1
}

install_rules() {
    if [ -e /etc/NIXOS ]; then
        say "NixOS: /etc is generated, so add the rules to configuration.nix and rebuild:"
        say "  services.udev.extraRules = builtins.readFile $SRC/udev/70-hyperx-linux.rules;"
        return 0
    fi
    if ! command -v udevadm >/dev/null 2>&1; then
        say "No udev found (mdev or none): give your user access to the HyperX /dev/hidraw* nodes manually,"
        say "or run hyperx-linux as root. See the README."
        return 0
    fi
    if uaccess_works; then
        rules=$(PYTHONPATH="$SRC" python3 -m hyperx_linux udev-rules)
    else
        say "No systemd-logind: access goes through the \"$GROUP\" group."
        rules=$(PYTHONPATH="$SRC" python3 -m hyperx_linux udev-rules --group "$GROUP")
        if ! getent group "$GROUP" >/dev/null 2>&1; then
            if command -v groupadd >/dev/null 2>&1; then as_root groupadd -r "$GROUP"
            else as_root addgroup -S "$GROUP"; fi
        fi
        if ! id -nG "$ME" | tr ' ' '\n' | grep -qx "$GROUP"; then
            if command -v usermod >/dev/null 2>&1; then as_root usermod -aG "$GROUP" "$ME"
            else as_root addgroup "$ME" "$GROUP"; fi
            say "Added $ME to \"$GROUP\": log out and back in for it to take effect."
        fi
    fi
    if [ "$(cat "$RULE" 2>/dev/null)" != "$rules" ]; then
        say "Installing udev rules…"
        printf '%s\n' "$rules" | as_root tee "$RULE" >/dev/null
        as_root udevadm control --reload-rules
        as_root udevadm trigger --action=change --subsystem-match=hidraw --subsystem-match=input --subsystem-match=misc
    fi
}

desktop_entry() {
    sed -e "s|@BIN@|$BIN|" -e "s|@ARGS@|$1|" -e "s|@ICON@|$APP_ID|" -e 's| $||' "$SRC/data/hyperx-linux.desktop.in"
}

uninstall() {
    rm -f "$BIN" "$APPS/$APP_ID.desktop" "$AUTOSTART/$APP_ID.desktop" "$ICON"
    rm -rf "$DOWNLOADED"
    rmdir "$DATA/hyperx-linux" 2>/dev/null || true
    if [ -e "$RULE" ]; then
        say "Removing udev rules…"
        if as_root rm -f "$RULE"; then as_root udevadm control --reload-rules || true
        else say "Couldn't remove $RULE: delete it as root."; fi
    fi
    say "Uninstalled. Settings are kept in ~/.config/hyperx-linux."
}

main() {
    want_autostart=1 want_deps=1 rules_only=
    for arg in "$@"; do
        case "$arg" in
            --no-autostart) want_autostart= ;;
            --no-deps) want_deps= ;;
            --rules-only) rules_only=1 ;;
            --uninstall) uninstall; return 0 ;;
            *) say "usage: install.sh [--no-autostart] [--no-deps] [--rules-only] [--uninstall]" >&2; exit 2 ;;
        esac
    done

    fetch_source "$@"
    if [ -n "$want_deps" ] && [ -z "$rules_only" ]; then install_deps; fi
    if ! python_ok; then
        say "Python 3.8 or newer is required (or use the Flatpak, see the README)."; exit 1
    fi
    if [ -n "$rules_only" ]; then install_rules; return 0; fi
    if ! gui_ok; then
        say "Note: GTK 4 / libadwaita for Python not found, so only the command line will work. To get the window:"
        deps_hint
        say "Distributions without GTK 4 (Debian 11, Ubuntu 20.04…) can use the Flatpak instead (see the README)."
    fi

    install_rules

    mkdir -p "$(dirname "$BIN")" "$APPS" "$AUTOSTART" "$(dirname "$ICON")"
    cat > "$BIN" <<EOF
#!/bin/sh
PYTHONPATH="$SRC\${PYTHONPATH:+:\$PYTHONPATH}" exec python3 -m hyperx_linux "\$@"
EOF
    chmod +x "$BIN"
    cp "$SRC/data/icons/$APP_ID.svg" "$ICON"
    desktop_entry "" > "$APPS/$APP_ID.desktop"
    if [ -n "$want_autostart" ]; then
        desktop_entry "--background" > "$AUTOSTART/$APP_ID.desktop"
    else
        rm -f "$AUTOSTART/$APP_ID.desktop"
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then update-desktop-database "$APPS" 2>/dev/null || true; fi

    say "Done. Open \"HyperX Linux\" from the app menu, or run 'hyperx-linux' (window) or 'hyperx-linux status' (terminal)."
    case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) say "Add ~/.local/bin to your PATH to use the command." ;; esac
}

main "$@"
