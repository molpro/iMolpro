import logging
import os
import pathlib
import platform

from OptionsDialog import OptionsDialog
from utilities import FileBackedDictionary

logger = logging.getLogger(__name__)

settings = FileBackedDictionary(
    str(pathlib.Path(
        os.environ['APPDATA' if platform.system() == 'Windows' else 'HOME']) / '.molpro' / 'iMolpro.settings.json'))


def settings_edit(parent=None, callbacks={}, hide=[]):
    box = OptionsDialog({k: settings[k] for k in settings if k not in hide},
                        ['CHEMSPIDER_API_KEY', 'mo_translucent', 'expertise'], title='Settings',
                        parent=parent)
    result = box.exec()
    if result is not None:
        for k in result:
            try:
                result[k] = int(result[k])
            except:
                try:
                    if type(result[k]) != int:
                        result[k] = float(result[k])
                except:
                    pass
            changed = k not in settings or settings[k] != result[k]
            settings[k] = result[k]
            logger.debug('Settings changed: {}'.format(settings))
            if changed and k in callbacks and callable(callbacks[k]):
                callbacks[k]()
        for k in settings:
            if k not in result:
                del settings[k]
