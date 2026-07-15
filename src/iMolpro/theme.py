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
except ImportError:
    try:
        from PyQt6.QtGui import QPalette, QColor
    except ImportError:
        from PyQt5.QtGui import QPalette, QColor

try:
    ColorRole = QPalette.ColorRole
except AttributeError:
    ColorRole = QPalette

# The traditional light-grey window background iMolpro has always shown
# (e.g. via conda-forge's PySide6 on macOS), applied explicitly rather than
# left to whichever native theme integration happens to be present.
LIGHT_GREY_WINDOW = QColor(0xec, 0xec, 0xec)


def build_light_palette():
    """Construct the default ('light') palette."""
    palette = QPalette()
    palette.setColor(ColorRole.Window, LIGHT_GREY_WINDOW)
    palette.setColor(ColorRole.Button, LIGHT_GREY_WINDOW)
    return palette


THEMES = {
    'light': build_light_palette,
}


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
