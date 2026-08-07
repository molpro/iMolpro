try:
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtWidgets import QApplication, QMenu
    from PySide6.QtGui import QActionGroup
except ImportError:
    try:
        from PyQt6.QtCore import QCoreApplication
        from PyQt6.QtWidgets import QApplication, QMenu
        from PyQt6.QtGui import QActionGroup
    except ImportError:
        from PyQt5.QtCore import QCoreApplication
        from PyQt5.QtWidgets import QApplication, QMenu
        from PyQt5.QtGui import QActionGroup

from .MenuBar import MenuBar
from .RecentMenu import RecentMenu
from .RunDirectoryMenu import RunDirectoryMenus
from .settings import settings, settings_edit
from .theme import THEMES, detect_system_theme
from .help import help_manager_default
from .backend import configure_backend
from .project import SLURM_OUTPUT_SUFFIX


def setup_project_window_menubar(window):
    menubar = MenuBar(window)
    window.setMenuBar(menubar)
    menubar.addAction('New', 'Projects', slot=window.new_action, shortcut='Ctrl+N',
                      tooltip='Create a new project')
    menubar.addAction('Close', 'Projects', window.close, 'Ctrl+W')
    menubar.addAction('Open', 'Projects', window.chooser_open, 'Ctrl+O', 'Open another project')
    menubar.addSeparator('Projects')
    window.recent_menu = RecentMenu(window.window_manager)
    menubar.addSubmenu(window.recent_menu, 'Projects')
    menubar.addSeparator('Projects')
    menubar.addAction('Move to...', 'Projects', window.move_to, tooltip='Move the project')
    menubar.addAction('Copy to...', 'Projects', window.copy_to, tooltip='Make a copy of the project')
    menubar.addAction('Erase', 'Projects', window.erase, tooltip='Completely erase the project')
    menubar.addSeparator('Projects')
    menubar.addAction('Quit', 'Projects', slot=QCoreApplication.quit, shortcut='Ctrl+Q',
                      tooltip='Quit')
    menubar.addAction('Import input', 'Files', window.import_input, 'Ctrl+Shift+I',
                      tooltip='Import a file and assign it as the input for the project')
    menubar.addAction('Import structure', 'Files', window.import_structure, 'Ctrl+Alt+I',
                      tooltip='Import an xyz file and use it as the source of molecular structure in the input for the project')
    menubar.addAction('Search external databases for structure', 'Files', window.database_import_structure,
                      'Ctrl+Shift+Alt+I',
                      tooltip='Search PubChem and ChemSpider for a molecule and use it as the source of molecular structure in the input for the project')
    # menubar.addAction('Adopt optimised structure from the most recent run', 'Files',
    #                   lambda dum, self=self: self.database_import_optimised(run=0, file='optimised.xyz'),
    #                   tooltip='Adopt structure from the most recent geometry optimisation')
    # menubar.addAction('Select a structure from a previous geometry optimisation...', 'Files',
    #                   self.database_import_optimised,
    #                   tooltip='Select a structure from a previous geometry optimisation')
    menubar.addAction('Convert xyz geometry to Z-matrix', 'Files',
                      window.convert_xyz_to_zmat,
                      tooltip='Convert xyz geometry to Z-matrix')
    window.xyz_to_zmat_activate_or_not(window.input_uses_xyz_file() is not None)
    menubar.addAction('Import file', 'Files', window.import_file, 'Ctrl+I',
                      tooltip='Import one or more files, eg geometry definition, into the project')
    menubar.addAction('Export file', 'Files', window.export_file, 'Ctrl+E',
                      tooltip='Export one or more files from the project')
    menubar.addAction('Clean', 'Files', window.clean, tooltip='Remove old runs from the project')

    window.run_directory_menus = RunDirectoryMenus(window, menubar, 'Runs')

    menubar.addAction('Settings', 'Edit',
                      lambda arg, parent=window: settings_edit(parent, {}),
                      tooltip='Edit settings')
    window.window_manager.set_cli_action_owner(menubar)
    menubar.addSeparator('Edit')
    if False and settings['use_jmol']:
        menubar.addAction('Structure', 'Edit', window.edit_input_structure, 'Ctrl+D', 'Edit molecular geometry')
    menubar.addAction('Cut', 'Edit', window.input_pane.cut, 'Ctrl+X', 'Cut')
    menubar.addAction('Copy', 'Edit', lambda: QApplication.focusWidget().copy(), 'Ctrl+C', 'Copy')
    menubar.addAction('Paste', 'Edit', window.input_pane.paste, 'Ctrl+V', 'Paste')
    menubar.addAction('Undo', 'Edit', window.input_pane.undo, 'Ctrl+Z', 'Undo')
    menubar.addAction('Redo', 'Edit', window.input_pane.redo, 'Shift+Ctrl+Z', 'Redo')
    menubar.addAction('Select All', 'Edit', window.input_pane.selectAll, 'Ctrl+A', 'Redo')
    menubar.addSeparator('Edit')
    menubar.addAction('Zoom In', 'Edit', window.input_pane.zoomIn, 'Ctrl++', 'Increase font size')
    menubar.addAction('Zoom Out', 'Edit', window.input_pane.zoomOut, 'Ctrl+-', 'Decrease font size')
    menubar.addSeparator('Edit')
    window.guided_action = menubar.addAction('Guided mode', 'Edit', window.guided_toggle, 'Ctrl+G', checkable=True)
    menubar.addAction('Show parsed input specification', 'Edit', window.show_input_specification, 'Shift+Ctrl+G')

    menubar.addSeparator('Files')
    menubar.addAction('Browse project folder', 'Files', window.browse_project, 'Ctrl+Alt+F',
                      tooltip='Look at the contents of the project folder.  With care, files can be edited or renamed, but note that this may break the integrity of the project.')
    menubar.addAction('Zoom In', 'View', lambda: [p.zoomIn() for p in window.output_panes.values()], 'Alt++',
                      'Increase font size')
    menubar.addAction('Zoom Out', 'View', lambda: [p.zoomOut() for p in window.output_panes.values()], 'Alt+-',
                      'Decrease font size')
    theme_menu = QMenu('Theme')
    theme_action_group = QActionGroup(window)
    theme_action_group.setExclusive(True)
    current_theme = settings['theme'] if 'theme' in settings else detect_system_theme(QApplication.instance())
    for theme_name in THEMES:
        action = theme_menu.addAction(theme_name.capitalize())
        action.setCheckable(True)
        action.setChecked(theme_name == current_theme)
        theme_action_group.addAction(action)
        action.triggered.connect(lambda checked, theme_name=theme_name: window.set_theme(theme_name))
    menubar.addSubmenu(theme_menu, 'View')
    menubar.addSeparator('View')
    # (action, instance) pairs consulted by update_view_menu_actions() to grey out actions
    # whose target file doesn't exist yet.
    window.view_xyz_actions = [
        (menubar.addAction('Initial structure xyz', 'View', window.show_xyz_input,
                           tooltip='View the xyz file for the molecular structure in the job input'), -1),
        (menubar.addAction('Final structure xyz', 'View', window.show_xyz_output,
                           tooltip='View the xyz file for the molecular structure at the end of the job'), 0),
    ]
    if window.external_viewer_commands:
        window.external_menu = QMenu('View molecule in external program...')
        for command in window.external_viewer_commands.keys():
            action = window.external_menu.addAction(command)
            action.triggered.connect(lambda dum, command=command: window.visualise_input(
                external_path=window.external_viewer_commands[command]))

        menubar.addSubmenu(window.external_menu, 'View')
    menubar.addSeparator('View')
    menubar.addAction('Next output tab', 'View', lambda: window.output_tabs.setCurrentIndex(
        (window.output_tabs.currentIndex() + 1) % len(window.output_tabs)), 'Alt+]')
    menubar.addAction('Previous output tab', 'View', lambda: window.output_tabs.setCurrentIndex(
        (window.output_tabs.currentIndex() - 1) % len(window.output_tabs)), 'Alt+[')

    menubar.addSeparator('View')
    # suffix -> action, consulted by update_view_menu_actions() to grey out actions whose
    # target file doesn't exist yet.
    window.view_file_actions = {
        'out': menubar.addAction('Job output', 'View', lambda: window.output_tabs.add_suffix('out'),
                                 shortcut='Alt+o'),
        'inp': menubar.addAction('Job input', 'View', lambda: window.output_tabs.add_suffix('inp'),
                                 shortcut='Alt+i'),
        'log': menubar.addAction('Job log', 'View', lambda: window.output_tabs.add_suffix('log'),
                                 shortcut='Alt+l'),
        'xml': menubar.addAction('Job xml', 'View', lambda: window.output_tabs.add_suffix('xml'),
                                 shortcut='Alt+x'),
        'stdout': menubar.addAction('Job stdout', 'View', lambda: window.output_tabs.add_suffix('stdout')),
        'stderr': menubar.addAction('Job stderr', 'View', lambda: window.output_tabs.add_suffix('stderr')),
        SLURM_OUTPUT_SUFFIX: menubar.addAction('Job Slurm output', 'View',
                                              lambda: window.output_tabs.add_suffix(SLURM_OUTPUT_SUFFIX)),
    }
    window.update_view_menu_actions()

    window.run_action = menubar.addAction('Run', 'Job', window.run, 'Ctrl+R', 'Run Molpro on the project input')
    window.run_force_action = menubar.addAction('Run (force)', 'Job', window.run_force, 'Ctrl+Shift+R',
                                                'Run Molpro on the project input, even if the input has not changed since the last run')
    window.kill_action = menubar.addAction('Kill', 'Job', window.kill, tooltip='Kill the running job')
    menubar.addAction('Backend', 'Job', lambda: configure_backend(window), 'Ctrl+B', 'Configure backend')
    menubar.addAction('Edit backend configuration file', 'Job', window.edit_backend_configuration, 'Ctrl+Shift+B',
                      'Edit backend configuration file')
    help_manager = help_manager_default(menubar)
    menubar.show()
