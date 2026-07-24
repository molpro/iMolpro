"""
Qt-dependent glue between cli_install.py's pure Python logic and the
menu/dialogs the user actually interacts with. Kept separate from
cli_install.py so that module stays plain Python/pathlib, easily
tested without a running Qt application.

Only one QAction for "Install command line tool..." is ever created
(see WindowManager.get_cli_install_action()). On macOS, Qt's
Application-menu merging recomputes which QAction::ApplicationSpecificRole
items to show from whichever top-level windows currently have such an
action somewhere in their own menu bar -- it does not de-duplicate by
the action's identity, so merely inserting the very same QAction
object into every window's menu bar still shows one copy per window
that has it. WindowManager.set_cli_action_owner() instead keeps the
action in exactly one window's menu bar at a time, moving it whenever
a different window becomes active (see the changeEvent overrides in
Chooser and ProjectWindow), which is the only way to get exactly one
instance regardless of how many windows are open.
"""
try:
    from PySide6.QtWidgets import QMessageBox, QApplication
    from PySide6.QtGui import QAction
except ImportError:
    try:
        from PyQt6.QtWidgets import QMessageBox, QApplication
        from PyQt6.QtGui import QAction
    except ImportError:
        from PyQt5.QtWidgets import QMessageBox, QApplication, QAction

try:
    ApplicationSpecificRole = QAction.ApplicationSpecificRole
except AttributeError:
    ApplicationSpecificRole = QAction.MenuRole.ApplicationSpecificRole

from . import cli_install


def make_cli_install_action():
    """Create the one-and-only QAction for this feature."""
    action = QAction('Install command line tool...')
    action.setToolTip("Make 'iMolpro' available as a command in Terminal")
    action.setMenuRole(ApplicationSpecificRole)
    action.triggered.connect(lambda checked=False: install_cli_tool(QApplication.activeWindow()))
    return action


def install_cli_tool(parent):
    if cli_install.already_installed():
        box = QMessageBox(parent)
        box.setWindowTitle('iMolpro command line tool')
        box.setText(f"The 'iMolpro' command is already installed at {cli_install.TARGET}.")
        reinstall_button = box.addButton('Reinstall', QMessageBox.ActionRole)
        remove_button = box.addButton('Remove', QMessageBox.DestructiveRole)
        cancel_button = box.addButton(QMessageBox.Cancel)
        box.setDefaultButton(reinstall_button)
        box.setEscapeButton(cancel_button)
        box.exec()
        clicked = box.clickedButton()
        if clicked is reinstall_button:
            try:
                QMessageBox.information(parent, 'iMolpro command line tool', cli_install.reinstall())
            except RuntimeError as e:
                QMessageBox.warning(parent, 'iMolpro command line tool',
                                    f'Could not reinstall the command line tool:\n{e}')
        elif clicked is remove_button:
            try:
                QMessageBox.information(parent, 'iMolpro command line tool', cli_install.uninstall())
            except RuntimeError as e:
                QMessageBox.warning(parent, 'iMolpro command line tool',
                                    f'Could not remove the command line tool:\n{e}')
        return

    try:
        message = cli_install.install()
    except cli_install.ExistingFileConflict:
        button = QMessageBox.question(
            parent, 'iMolpro command line tool',
            f'{cli_install.TARGET} already exists and is not the iMolpro command line tool.'
            '\n\nOverwrite it?',
            QMessageBox.Yes | QMessageBox.No, defaultButton=QMessageBox.Yes)
        if button != QMessageBox.Yes:
            return
        try:
            message = cli_install.install(overwrite=True)
        except RuntimeError as e:
            QMessageBox.warning(parent, 'iMolpro command line tool',
                                f'Could not install the command line tool:\n{e}')
            return
    except RuntimeError as e:
        QMessageBox.warning(parent, 'iMolpro command line tool',
                            f'Could not install the command line tool:\n{e}')
        return

    QMessageBox.information(
        parent, 'iMolpro command line tool',
        message + "\n\nOpen a new Terminal window and type 'iMolpro' to launch the app, "
                  "or 'iMolpro myproject.molpro' to open a project directly.")
