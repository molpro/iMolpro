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


def detect_system_theme(app, default: str = 'light') -> str:
    """Detect the OS's light/dark preference, falling back to `default`.

    Uses QGuiApplication.styleHints().colorScheme(), Qt's cross-platform
    (Windows/macOS/Linux) way of reading this -- added in Qt 6.5, so this
    falls back gracefully on older Qt, or on a binding (e.g. PyQt5) that
    doesn't have it at all.
    """
    try:
        from PySide6.QtCore import Qt as _Qt
    except ImportError:
        try:
            from PyQt6.QtCore import Qt as _Qt
        except ImportError:
            return default
    try:
        scheme = app.styleHints().colorScheme()
    except AttributeError:
        return default
    if scheme == _Qt.ColorScheme.Dark:
        return 'dark'
    if scheme == _Qt.ColorScheme.Light:
        return 'light'
    return default


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
    theme_manager.themeChanged.emit(name)
