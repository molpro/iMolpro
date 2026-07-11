# Check whether a specific PyQt implementation was chosen
global PyQtImpl, QVTKRWIBase
try:
    print('importing vtkmodules.qt')
    import vtkmodules.qt
    PyQtImpl = vtkmodules.qt.PyQtImpl
except ImportError:
    print('vtkmodules.qt not found')
    pass
print('finished importing vtkmodules.qt')

# Check whether a specific QVTKRenderWindowInteractor base
# class was chosen, can be set to "QGLWidget" in
# PyQt implementation version lower than Qt6,
# or "QOpenGLWidget" in Pyside6 and PyQt6
QVTKRWIBase = "QWidget"
try:
    import vtkmodules.qt
    QVTKRWIBase = vtkmodules.qt.QVTKRWIBase
except ImportError:
    pass

from vtkmodules.vtkRenderingCore import vtkRenderWindow
from vtkmodules.vtkRenderingUI import vtkGenericRenderWindowInteractor

if PyQtImpl is None:
    # Autodetect the PyQt implementation to use
    try:
        import PySide6.QtCore
        PyQtImpl = "PySide6"
    except ImportError:
        try:
            import PyQt6.QtCore
            PyQtImpl = "PyQt6"
        except ImportError:
            try:
                import PyQt5.QtCore
                PyQtImpl = "PyQt5"
            except ImportError:
                try:
                    import PySide2.QtCore
                    PyQtImpl = "PySide2"
                except ImportError:
                    try:
                        import PyQt4.QtCore
                        PyQtImpl = "PyQt4"
                    except ImportError:
                        try:
                            import PySide.QtCore
                            PyQtImpl = "PySide"
                        except ImportError:
                            raise ImportError("Cannot load either PyQt or PySide")

# globals()[PyQtImpl] = __import__(PyQtImpl)
# PyQt = globals()[PyQtImpl]
print("PyQtImpl: ", PyQtImpl, " QVTKRWIBase: ", QVTKRWIBase)