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
