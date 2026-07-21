import logging
import pathlib

from .OptionsDialog import OptionsDialog
from .utilities import FileBackedDictionary

logger = logging.getLogger(__name__)

settings = FileBackedDictionary(str(pathlib.Path.home() / '.molpro' / 'iMolpro.settings.json'))


def settings_edit(parent=None, callbacks=None):
    if callbacks is None:
        callbacks = {}
    hide = ['project_window_width', 'project_window_height']
    visible_settings = {k: settings[k] for k in settings if k not in hide}
    available_options = ['CHEMSPIDER_API_KEY']
    available_options += [k for k in settings.defaults if k not in visible_settings and k not in available_options]
    box = OptionsDialog(visible_settings, available_options, title='Settings', parent=parent)
    result = box.exec()
    if result is not None:
        for k, v in result.items():
            original = settings.get(k)
            try:
                v = int(v)
            except (ValueError, TypeError):
                try:
                    v = float(v)
                except (ValueError, TypeError):
                    pass
            changed = original != v
            settings[k] = v
            if changed:
                logger.debug(f'Setting changed: {k} = {v}')
                if k in callbacks and callable(callbacks[k]):
                    callbacks[k]()
        to_delete = [k for k in settings if k not in result]
        for k in to_delete:
            del settings[k]
