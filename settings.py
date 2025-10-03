import logging
import pathlib

from OptionsDialog import OptionsDialog
from utilities import FileBackedDictionary

logger = logging.getLogger(__name__)

settings = FileBackedDictionary(str(pathlib.Path.home() / '.molpro' / 'iMolpro.settings.json'))


def settings_edit(parent=None, callbacks=None):
    if callbacks is None:
        callbacks = {}
    hide = ['project_window_width', 'project_window_height']
    visible_settings = {k: settings[k] for k in settings if k not in hide}
    box = OptionsDialog(visible_settings, [
        'CHEMSPIDER_API_KEY',
        'orbital_transparency',
    ], title='Settings', parent=parent)
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
