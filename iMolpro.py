import pathlib

from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QMessageBox
import sys

from Chooser import Chooser
from ProjectWindow import ProjectWindow
from WindowManager import WindowManager
import os
import platform
import logging

if __name__ == '__main__':

    class App(QApplication):
        def event(self, e):
            if e.type() == QEvent.FileOpen and os.path.splitext(e.file())[1] == '.molpro':
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
        for env in ['TMPDIR', 'TMP', 'TEMP', 'SCRATCH']:
            if env in os.environ and os.access(os.environ[env], os.W_OK):
                filename = str(pathlib.Path(os.environ[env]) / 'iMolpro.log')
                if os.path.exists(filename):
                    os.remove(filename)
                logging.basicConfig(filename=filename,
                                    level=log_level,
                                    format='%(asctime)s %(levelname)-8s %(name)s %(funcName)s() %(pathname)s:%(lineno)d %(message)s',
                                    datefmt='%Y-%m-%d %H:%M:%S')
                sys.stdout = open(str(pathlib.Path(os.environ[env]) / 'iMolpro.stdout'), 'w')
                sys.stderr = open(str(pathlib.Path(os.environ[env]) / 'iMolpro.stderr'), 'w')
                break
    else:
        logging.basicConfig(level=log_level,
                            format='%(asctime)s %(levelname)-8s %(name)s %(funcName)s() %(pathname)s:%(lineno)d %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S')
    logger.info('iMolpro starting...')

    if platform.uname().system == 'Linux':
        if 'FONTCONFIG_PATH' not in os.environ:
            os.environ['FONTCONFIG_PATH'] = '/etc/fonts'
        if 'FONTCONFIG_FILE' not in os.environ:
            os.environ['FONTCONFIG_FILE'] = '/etc/fonts/fonts.conf'

    try:
        if platform.uname().system == 'Windows':
            os.environ['PATH'] = os.path.dirname(os.path.abspath(__file__)) + ';' + os.environ['PATH']
            if 'CONDA_PREFIX' not in os.environ:
                os.environ['CONDA_PREFIX'] = os.path.dirname(os.path.abspath(__file__))
        elif 'PATH' in os.environ and 'SHELL' in os.environ:
            os.environ['PATH'] = os.popen(os.environ['SHELL'] + " -l -c 'echo $PATH'").read() + ':' + os.environ[
                'PATH']  # make PATH just as if running from shell
    except Exception as e:
        msg = QMessageBox()
        msg.setText('Error in setting PATH')
        msg.setDetailedText(str(e))
        msg.exec()

    if platform.uname().system == 'Windows':
        if 'CONDA_PREFIX' in os.environ:
            os.environ['PATH'] = str(pathlib.Path(os.environ['CONDA_PREFIX']) / 'bin') + ';' + os.environ['PATH']
        import ctypes
        import ctypes.wintypes

        console_window = ctypes.windll.kernel32.GetConsoleWindow()
        if console_window:
            process_id = ctypes.windll.kernel32.GetCurrentProcessId()
            console_process_id = ctypes.wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(console_window, ctypes.byref(console_process_id))
            console_process_id = console_process_id.value
            if process_id == console_process_id:
                ctypes.windll.user32.ShowWindow(console_window, 2)

    app = App(sys.argv)
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
    logger.info('... iMolpro stopping')
