import os
import pathlib
import platform

from OptionsDialog import OptionsDialog
from utilities import FileBackedDictionary

settings = FileBackedDictionary(
    str(pathlib.Path(
        os.environ['APPDATA' if platform.system() == 'Windows' else 'HOME']) / '.molpro' / 'iMolpro.settings.json'))


def settings_edit(parent=None):
    box = OptionsDialog(dict(settings), ['CHEMSPIDER_API_KEY', 'mo_translucent', 'expertise'], title='Settings',
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
            settings[k] = result[k]
        for k in settings:
            if k not in result:
                del settings[k]
