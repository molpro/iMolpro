import pathlib
import os
import platform
import sys

from ._paths import app_root

# This must run before importing any iMolpro submodule that transitively
# imports pymolpro/pysjef (.Chooser, .ProjectWindow, .WindowManager below):
# the compiled sjef library appears to resolve/cache PATH-dependent state
# (eg where to find the bundled Molpro executable) the first time it's
# touched, so a PATH fixup applied any later -- even at the top of main(),
# let alone per-window in ProjectWindow.ensure_local_molpro() -- arrives too
# late to take effect. Symptom when it's too late: job submission fails with
# (on Windows) "CreateProcess failed: The system cannot find the path
# specified" even though os.environ['PATH'] itself, inspected afterwards,
# looks correct.
try:
    if platform.uname().system == 'Windows':
        os.environ['PATH'] = str(app_root()) + os.pathsep + os.environ['PATH']
        if 'CONDA_PREFIX' not in os.environ:
            os.environ['CONDA_PREFIX'] = str(app_root())
        os.environ['PATH'] = str(pathlib.Path(os.environ['CONDA_PREFIX']) / 'bin') + os.pathsep + os.environ['PATH']
    elif 'PATH' in os.environ and 'SHELL' in os.environ:
        os.environ['PATH'] = os.popen(os.environ['SHELL'] + " -l -c 'echo $PATH'").read() + os.pathsep + \
                             os.environ['PATH']  # make PATH just as if running from shell
    molpro_bin = app_root() / 'molpro' / 'bin'
    if molpro_bin.is_dir():
        s = str(molpro_bin)
        if s not in os.environ.get('PATH', '').split(os.pathsep):
            os.environ['PATH'] = s + os.pathsep + os.environ.get('PATH', '')
except Exception as _e:
    # Too early for a QMessageBox (no QApplication yet) -- this mirrors the
    # equivalent fallback that used to live in main(), just downgraded to a
    # plain stderr print since it can no longer show a dialog here.
    print(f'Error in setting PATH: {_e}', file=sys.stderr)

try:
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication, QWidget, QPushButton
except ImportError:
    try:
        from PyQt6.QtCore import QEvent
        from PyQt6.QtWidgets import QApplication, QWidget, QPushButton
    except ImportError:
        from PyQt5.QtCore import QEvent
        from PyQt5.QtWidgets import QApplication, QWidget, QPushButton

try:
    QEvent_Type = QEvent.Type
except:
    QEvent_Type = QEvent

from .Chooser import Chooser
from .ProjectWindow import ProjectWindow
from .WindowManager import WindowManager
import logging

from .utilities import writable_directory
from .settings import settings


def main():
    class App(QApplication):
        def event(self, e):
            if e.type() == QEvent_Type.FileOpen and os.path.splitext(e.file())[1] in ['.molpro', '.out', '.inp', '.xml']:
                window_manager.register(ProjectWindow(e.file(), window_manager))
            else:
                return super().event(e)
            return True

    logger = logging.getLogger(__name__)
    log_level = logging.INFO
    if 'LOGGING_LEVEL' in os.environ and os.environ['LOGGING_LEVEL'] == 'NOTSET': log_level = logging.NOTSET
    if 'LOGGING_LEVEL' in os.environ and os.environ['LOGGING_LEVEL'] == 'DEBUG': log_level = logging.DEBUG
    if 'LOGGING_LEVEL' in os.environ and os.environ['LOGGING_LEVEL'] == 'INFO': log_level = logging.INFO
    if 'LOGGING_LEVEL' in os.environ and os.environ['LOGGING_LEVEL'] == 'WARNING': log_level = logging.WARNING
    if 'LOGGING_LEVEL' in os.environ and os.environ['LOGGING_LEVEL'] == 'ERROR': log_level = logging.ERROR
    if 'LOGGING_LEVEL' in os.environ and os.environ['LOGGING_LEVEL'] == 'CRITICAL': log_level = logging.CRITICAL
    if hasattr(sys, '_MEIPASS'):
        tmpdir = writable_directory()
        filename = str(tmpdir / 'iMolpro.log')
        if os.path.exists(filename):
            os.remove(filename)
        logging.basicConfig(filename=filename,
                            level=log_level,
                            format='%(asctime)s %(levelname)-8s %(name)s %(funcName)s() %(pathname)s:%(lineno)d %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S')
        sys.stdout = open(str(tmpdir / 'iMolpro.stdout'), 'w')
        sys.stderr = open(str(tmpdir / 'iMolpro.stderr'), 'w')
    else:
        logging.basicConfig(level=log_level,
                            format='%(asctime)s %(levelname)-8s %(name)s %(funcName)s() %(pathname)s:%(lineno)d %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S')
    logger.debug('iMolpro starting...')
    logger.debug(f'PATH={os.environ.get("PATH", "")}')

    if platform.uname().system == 'Linux':
        if 'FONTCONFIG_PATH' not in os.environ:
            os.environ['FONTCONFIG_PATH'] = '/etc/fonts'
        if 'FONTCONFIG_FILE' not in os.environ:
            os.environ['FONTCONFIG_FILE'] = '/etc/fonts/fonts.conf'
        if 'QT_QPA_PLATFORM' not in os.environ:
            # VTK's OpenGL rendering (vtkXOpenGLRenderWindow) is Xlib-based
            # and does raw X11 window calls; under Qt's native Wayland
            # platform plugin there is no X11 window for it to get a handle
            # to at all, causing a fatal X11 protocol error (BadWindow) the
            # moment a VTK-containing window is opened. Forcing xcb runs
            # through XWayland instead, like a normal X11 app, which VTK's
            # X11 backend can actually interoperate with.
            os.environ['QT_QPA_PLATFORM'] = 'xcb'

    if platform.uname().system == 'Windows' and os.environ.get('IMOLPRO_KEEP_CONSOLE') != '1':
        import ctypes
        import ctypes.wintypes

        console_window = ctypes.windll.kernel32.GetConsoleWindow()
        if console_window:
            process_id = ctypes.windll.kernel32.GetCurrentProcessId()
            console_process_id = ctypes.wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(console_window, ctypes.byref(console_process_id))
            console_process_id = console_process_id.value
            if process_id == console_process_id:
                # Free the console entirely rather than just minimising it.
                # sys.stdout/sys.stderr are already redirected to log files
                # above, so iMolpro has no further use for this console --
                # and leaving the process attached to it (even minimised)
                # is a plausible source of unexpected behaviour in spawned
                # child processes (e.g. the MSYS2-based nohup/bash used for
                # local job submission), which was only ever observed when
                # this console was freshly auto-allocated (a double-clicked
                # frozen exe with no parent terminal to inherit from) and
                # not when launched from an existing terminal.
                ctypes.windll.kernel32.FreeConsole()

    # Suppress a known-benign Qt/Windows cosmetic warning
    # ("QWindowsWindow::setGeometry: Unable to set geometry...") that Qt
    # logs whenever it has to adjust a *native* child widget's geometry
    # (e.g. a QSplitter promoted to a native window by containing VTK/
    # OpenGL content) to fit Windows' own constraints. This is an internal
    # Qt layout/platform interaction, unrelated to and unaffected by any
    # application-level window sizing -- harmless, but noisy on every
    # startup. Append to any existing rules rather than overwriting them.
    existing_qt_logging_rules = os.environ.get('QT_LOGGING_RULES', '')
    qpa_window_suppression = 'qt.qpa.window=false'
    os.environ['QT_LOGGING_RULES'] = (
        existing_qt_logging_rules + ';' + qpa_window_suppression
        if existing_qt_logging_rules else qpa_window_suppression
    )

    app = App(sys.argv)
    from .theme import apply_theme, detect_system_theme
    default_theme = settings['theme'] if 'theme' in settings else detect_system_theme(app)
    theme_name = os.environ.get('IMOLPRO_THEME', default_theme)
    apply_theme(app, theme_name)
    if platform.uname().system == 'Windows':
        font = app.font()
        font.setPointSize(7)
        app.setFont(font)

    window_manager = WindowManager()
    chooser = Chooser(window_manager)
    chooser.quitButton.clicked.connect(app.quit)
    window_manager.set_empty_action(chooser.activate)
    window_manager.set_full_action(chooser.hide)

    for arg in sys.argv[1:]:
        window_manager.register(ProjectWindow(arg, window_manager))

    app.exec()
    logger.debug('... iMolpro stopping')


if __name__ == '__main__':
    main()
