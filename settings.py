import os
import platform
from utilities import FileBackedDictionary

settings = FileBackedDictionary(
    os.environ['APPDATA' if platform.system() == 'Windows' else 'HOME'] + '/.molpro/iMolpro.settings.json')
