"""Detect a missing/unusable OpenGL driver and explain it to the user.

VTK needs a working OpenGL context to draw molecules. On machines without a
usable driver (typically a virtual machine without 3D acceleration) VTK
reports cryptic errors -- "failed to get valid pixel format", "osmesa.dll not
found" -- and, on Windows, pops them up in a raw dialog. This module quiets
those raw popups and shows one explanatory message instead.
"""
import logging
import sys

try:
    from PySide6.QtWidgets import QMessageBox, QApplication
except ImportError:
    try:
        from PyQt6.QtWidgets import QMessageBox, QApplication
    except ImportError:
        from PyQt5.QtWidgets import QMessageBox, QApplication

logger = logging.getLogger(__name__)

_available = None  # cached result of the probe
_warned = False


def quiet_vtk_output():
    """Send VTK diagnostics to stderr instead of a modal popup window."""
    try:
        from vtkmodules.vtkCommonCore import vtkOutputWindow
        vtkOutputWindow.GetInstance().SetDisplayMode(vtkOutputWindow.ALWAYS_STDERR)
    except Exception:  # older VTK without display modes
        logger.debug("Could not redirect VTK output window", exc_info=True)


def _wgl_has_modern_opengl() -> bool:
    """Windows: can we get a context that exposes wglChoosePixelFormatARB?

    That is exactly the entry point VTK needs and fails to find when there is no
    OpenGL driver (Windows' built-in GDI OpenGL 1.1 lacks it). VTK's own
    SupportsOpenGL() cannot be used: it reports success when it falls back to a
    missing OSMesa, and rendering in that state crashes the process.
    """
    import ctypes
    from ctypes import wintypes

    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    opengl32 = ctypes.windll.opengl32
    P = ctypes.c_void_p
    user32.CreateWindowExW.restype = P
    user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       P, P, P, P]
    user32.GetDC.restype = P
    user32.GetDC.argtypes = [P]
    user32.ReleaseDC.argtypes = [P, P]
    user32.DestroyWindow.argtypes = [P]
    gdi32.ChoosePixelFormat.argtypes = [P, P]
    gdi32.SetPixelFormat.argtypes = [P, ctypes.c_int, P]
    opengl32.wglCreateContext.restype = P
    opengl32.wglCreateContext.argtypes = [P]
    opengl32.wglMakeCurrent.argtypes = [P, P]
    opengl32.wglDeleteContext.argtypes = [P]
    opengl32.wglGetProcAddress.restype = P
    opengl32.wglGetProcAddress.argtypes = [ctypes.c_char_p]

    class PIXELFORMATDESCRIPTOR(ctypes.Structure):
        _fields_ = [("nSize", wintypes.WORD), ("nVersion", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("iPixelType", ctypes.c_ubyte), ("cColorBits", ctypes.c_ubyte),
                    ("cRedBits", ctypes.c_ubyte), ("cRedShift", ctypes.c_ubyte),
                    ("cGreenBits", ctypes.c_ubyte), ("cGreenShift", ctypes.c_ubyte),
                    ("cBlueBits", ctypes.c_ubyte), ("cBlueShift", ctypes.c_ubyte),
                    ("cAlphaBits", ctypes.c_ubyte), ("cAlphaShift", ctypes.c_ubyte),
                    ("cAccumBits", ctypes.c_ubyte), ("cAccumRedBits", ctypes.c_ubyte),
                    ("cAccumGreenBits", ctypes.c_ubyte), ("cAccumBlueBits", ctypes.c_ubyte),
                    ("cAccumAlphaBits", ctypes.c_ubyte), ("cDepthBits", ctypes.c_ubyte),
                    ("cStencilBits", ctypes.c_ubyte), ("cAuxBuffers", ctypes.c_ubyte),
                    ("iLayerType", ctypes.c_ubyte), ("bReserved", ctypes.c_ubyte),
                    ("dwLayerMask", wintypes.DWORD), ("dwVisibleMask", wintypes.DWORD),
                    ("dwDamageMask", wintypes.DWORD)]

    PFD_DRAW_TO_WINDOW, PFD_SUPPORT_OPENGL, PFD_DOUBLEBUFFER = 0x4, 0x20, 0x1
    pfd = PIXELFORMATDESCRIPTOR()
    pfd.nSize = ctypes.sizeof(pfd)
    pfd.nVersion = 1
    pfd.dwFlags = PFD_DRAW_TO_WINDOW | PFD_SUPPORT_OPENGL | PFD_DOUBLEBUFFER
    pfd.cColorBits, pfd.cDepthBits = 32, 24

    hwnd = user32.CreateWindowExW(0, "STATIC", "iMolpro-gl-probe", 0, 0, 0, 16, 16, None, None, None, None)
    if not hwnd:
        return False
    hdc = user32.GetDC(hwnd)
    ctx = None
    try:
        fmt = gdi32.ChoosePixelFormat(hdc, ctypes.byref(pfd))
        if not fmt or not gdi32.SetPixelFormat(hdc, fmt, ctypes.byref(pfd)):
            return False
        ctx = opengl32.wglCreateContext(hdc)
        if not ctx or not opengl32.wglMakeCurrent(hdc, ctx):
            return False
        return bool(opengl32.wglGetProcAddress(b"wglChoosePixelFormatARB"))
    finally:
        if ctx:
            opengl32.wglMakeCurrent(None, None)
            opengl32.wglDeleteContext(ctx)
        user32.ReleaseDC(hwnd, hdc)
        user32.DestroyWindow(hwnd)


def opengl_available() -> bool:
    """False if OpenGL is known to be unusable. Assumes True where it cannot tell (non-Windows,
    or if the probe itself fails)."""
    global _available
    if _available is None:
        _available = True
        if sys.platform == 'win32':
            try:
                _available = _wgl_has_modern_opengl()
            except Exception:
                logger.debug("OpenGL probe failed; assuming OpenGL is available", exc_info=True)
    return _available


def _advice() -> str:
    if sys.platform == 'win32':
        return ("If this is a virtual machine, enable 3D/GPU acceleration for it, or install a software "
                "OpenGL renderer: copy Mesa's opengl32.dll, libgallium_wgl.dll and dxil.dll "
                "(from https://github.com/pal1000/mesa-dist-win) into the folder containing the iMolpro "
                "executable. On a physical PC, installing the current graphics driver from your "
                "GPU vendor should fix it.")
    if sys.platform == 'darwin':
        return "Please check that your macOS graphics drivers are working."
    return ("Please install your GPU's OpenGL driver, or a software renderer such as Mesa "
            "(e.g. the libgl1-mesa-dri package).")


def warn_if_opengl_unavailable(parent=None) -> bool:
    """Show a one-time explanatory dialog if OpenGL is unusable. Returns the availability."""
    global _warned
    quiet_vtk_output()
    ok = opengl_available()
    if not ok and not _warned and QApplication.instance() is not None:
        _warned = True
        box = QMessageBox(parent)
        box.setIcon(QMessageBox.Icon.Warning if hasattr(QMessageBox, 'Icon') else QMessageBox.Warning)
        box.setWindowTitle("3D graphics unavailable")
        box.setText("iMolpro cannot display molecules because no usable OpenGL graphics support was found.")
        box.setInformativeText(_advice() + "\n\nYou can still edit inputs and run jobs; only the 3D view "
                                           "will not work.")
        box.exec() if hasattr(box, 'exec') else box.exec_()
    return ok
