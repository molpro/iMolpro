"""
Application-wide colour theme.

This applies an explicit style and palette, rather than relying on whatever
the native Qt platform theme happens to do. That native-theming reliance was
found to differ between a conda-forge-built PySide6 and the PyPI wheel on
macOS: same PySide6 version (6.9.3), same QStyle ('macos'), but a white
window background from the pip install versus the light grey iMolpro has
always shown from conda -- apparently because the two Qt builds' native
Cocoa theme integration resolve QPalette::Window differently, for reasons
outside iMolpro's control.

Using the platform-independent 'Fusion' style with an explicitly-constructed
QPalette sidesteps that whole category of difference: the same colours are
used regardless of how PySide6 itself was packaged, or which OS it runs on.
It also gives a single, obvious place to make the theme user-configurable
later (e.g. a Theme menu offering additional palettes built the same way).
"""
try:
    from PySide6.QtGui import QPalette, QColor
    from PySide6.QtCore import QObject, Signal as pyqtSignal
except ImportError:
    try:
        from PyQt6.QtGui import QPalette, QColor
        from PyQt6.QtCore import QObject, pyqtSignal
    except ImportError:
        from PyQt5.QtGui import QPalette, QColor
        from PyQt5.QtCore import QObject, pyqtSignal

try:
    ColorRole = QPalette.ColorRole
    ColorGroup = QPalette.ColorGroup
except AttributeError:
    ColorRole = QPalette
    ColorGroup = QPalette

# The traditional light-grey window background iMolpro has always shown
# (e.g. via conda-forge's PySide6 on macOS), applied explicitly rather than
# left to whichever native theme integration happens to be present.
LIGHT_GREY_WINDOW = QColor(0xec, 0xec, 0xec)
DARK_GREY_WINDOW = QColor(53, 53, 53)


def build_light_palette():
    """Construct the default ('light') palette."""
    palette = QPalette()
    palette.setColor(ColorRole.Window, LIGHT_GREY_WINDOW)
    palette.setColor(ColorRole.Button, LIGHT_GREY_WINDOW)
    return palette


def build_dark_palette():
    """Construct a 'dark' palette.

    This is the widely-used Fusion dark-palette recipe (the same handful of
    colours that show up in most Qt dark-theme examples). Unlike the light
    palette above, a dark theme needs most colour roles set explicitly:
    Fusion's own defaults for any role you *don't* set are light-theme
    colours, so e.g. leaving Text/WindowText unset here would give dark
    (near-black) text on a dark background -- unreadable. The light palette
    above gets away with only setting Window/Button because every other
    role's Fusion default already looks fine against a light background.
    """
    palette = QPalette()
    palette.setColor(ColorRole.Window, DARK_GREY_WINDOW)
    palette.setColor(ColorRole.WindowText, QColor(255, 255, 255))
    palette.setColor(ColorRole.Base, QColor(35, 35, 35))
    palette.setColor(ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(ColorRole.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(ColorRole.ToolTipText, QColor(255, 255, 255))
    palette.setColor(ColorRole.Text, QColor(255, 255, 255))
    palette.setColor(ColorRole.Button, DARK_GREY_WINDOW)
    palette.setColor(ColorRole.ButtonText, QColor(255, 255, 255))
    palette.setColor(ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(ColorRole.HighlightedText, QColor(0, 0, 0))
    # Without these, disabled widgets (e.g. a greyed-out button) would use
    # the same white text as enabled ones and become unreadable.
    palette.setColor(ColorGroup.Disabled, ColorRole.WindowText, QColor(127, 127, 127))
    palette.setColor(ColorGroup.Disabled, ColorRole.Text, QColor(127, 127, 127))
    palette.setColor(ColorGroup.Disabled, ColorRole.ButtonText, QColor(127, 127, 127))
    return palette


THEMES = {
    'light': build_light_palette,
    'dark': build_dark_palette,
}


class _ThemeManager(QObject):
    """Notifies subscribers when the app theme changes.

    QApplication.setPalette() only updates widgets that haven't had their
    own palette explicitly set -- any widget that calls setPalette() or
    setStyleSheet() on itself (or a child) 'locks in' that appearance and
    stops following the application palette. Such widgets should connect to
    themeChanged and re-apply their own colours from the new theme.
    """
    themeChanged = pyqtSignal(str)


theme_manager = _ThemeManager()


def _detect_linux_desktop_theme():
    """Fallback dark/light detection for Linux, where Qt's own
    styleHints().colorScheme() often returns Unknown -- it depends on the
    desktop environment's Qt platform integration correctly reporting the
    preference, which is much less consistently wired up than on macOS or
    Windows. Returns 'dark', 'light', or None if neither method below can
    determine it (e.g. not on Linux, or neither tool is available).
    """
    import platform
    import subprocess
    if platform.system() != 'Linux':
        return None
    # 1. The freedesktop XDG Desktop Portal 'Settings' interface -- the
    # standard, desktop-environment-agnostic mechanism, implemented by both
    # GNOME and KDE (via their respective portal backends). Queried via
    # gdbus (part of glib, present on essentially any Linux desktop with
    # GNOME or KDE installed) rather than adding a Python D-Bus dependency.
    try:
        result = subprocess.run(
            ['gdbus', 'call', '--session', '--dest', 'org.freedesktop.portal.Desktop',
             '--object-path', '/org/freedesktop/portal/desktop',
             '--method', 'org.freedesktop.portal.Settings.Read',
             'org.freedesktop.appearance', 'color-scheme'],
            capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            # Output looks like "(<<uint32 1>>,)" -- 1 means prefer dark,
            # 2 means prefer light, 0 means no preference.
            if 'uint32 1' in result.stdout:
                return 'dark'
            if 'uint32 2' in result.stdout:
                return 'light'
    except (OSError, subprocess.SubprocessError):
        pass
    # 2. GNOME-specific fallback (Fedora Workstation's default desktop),
    # for systems where the portal call above isn't available.
    try:
        result = subprocess.run(
            ['gsettings', 'get', 'org.gnome.desktop.interface', 'color-scheme'],
            capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and 'dark' in result.stdout.lower():
            return 'dark'
        if result.returncode == 0:
            return 'light'
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def detect_system_theme(app, default: str = 'light') -> str:
    """Detect the OS's light/dark preference, falling back to `default`.

    Uses QGuiApplication.styleHints().colorScheme(), Qt's cross-platform
    (Windows/macOS/Linux) way of reading this -- added in Qt 6.5, so this
    falls back gracefully on older Qt, or on a binding (e.g. PyQt5) that
    doesn't have it at all. On Linux, where this often reports Unknown
    regardless of Qt version (depends on the desktop environment's Qt
    platform integration), falls back further to _detect_linux_desktop_theme()
    before finally giving up and returning `default`.
    """
    try:
        from PySide6.QtCore import Qt as _Qt
    except ImportError:
        try:
            from PyQt6.QtCore import Qt as _Qt
        except ImportError:
            linux_theme = _detect_linux_desktop_theme()
            return linux_theme if linux_theme is not None else default
    try:
        scheme = app.styleHints().colorScheme()
    except AttributeError:
        linux_theme = _detect_linux_desktop_theme()
        return linux_theme if linux_theme is not None else default
    if scheme == _Qt.ColorScheme.Dark:
        return 'dark'
    if scheme == _Qt.ColorScheme.Light:
        return 'light'
    linux_theme = _detect_linux_desktop_theme()
    return linux_theme if linux_theme is not None else default


def apply_theme(app, name: str = 'light'):
    """Apply a named theme to the given QApplication.

    Uses the 'Fusion' style so that the resulting appearance is
    deterministic and identical regardless of platform or how the Qt
    binding was packaged (conda vs. pip), rather than depending on native
    platform theme integration.
    """
    app.setStyle('Fusion')
    try:
        build_palette = THEMES[name]
    except KeyError:
        raise ValueError(f'Unknown theme {name!r}; available: {sorted(THEMES)}')
    app.setPalette(build_palette())
    # Any widget that's ever had setStyleSheet() called on it -- even for
    # something unrelated to colour, like a font-size tweak -- switches to
    # CSS-based rendering internally and stops fully auto-updating with the
    # setPalette() call above unless explicitly re-polished. Repolish every
    # existing widget to force them all to recompute their appearance
    # against the new palette.
    #
    # Each widget's polish/update is wrapped in its own try/except: some
    # widget subclasses (e.g. QListView, used internally by QComboBox's
    # popup) override update() with a required-argument overload
    # (update(QModelIndex)) that shadows QWidget's plain update() in this
    # binding, raising TypeError. Uncaught, that would silently abort this
    # loop partway through on the first such widget encountered, leaving
    # every widget after it in app.allWidgets()'s (unordered) iteration
    # unprocessed -- which widgets that ended up being varied from one
    # theme switch to the next, giving an inconsistent, seemingly-inverted
    # appearance that had nothing to do with palette colours at all.
    for widget in app.allWidgets():
        try:
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
        except TypeError:
            pass
    theme_manager.themeChanged.emit(name)
