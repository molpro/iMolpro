"""
Make ``iMolpro`` available as a Terminal command on macOS, the same way
VS Code's "Shell Command: Install 'code' command in PATH" works.

Background: PyInstaller's ``--windowed`` macOS build produces
``iMolpro.app``. Its ``Contents/MacOS/iMolpro`` is the actual native
executable -- not a wrapper -- and is directly runnable from a shell,
so the simplest implementation of "install a command-line script"
would just be a symlink to it. That, however, launches a brand new
process every time it's invoked, giving multiple independent instances
of the app running at once. Instead, the installed command is a small
wrapper that calls ``/usr/bin/open -a iMolpro.app``, which is how
Finder and Launchpad start the app themselves: macOS routes the
request to the single already-running instance if there is one, and
only starts a fresh process if none was running.

Getting file arguments there correctly is more subtle than it first
looks. ``open -a Bundle --args file...`` only ever affects a freshly
*launched* process -- the arguments become that new process's argv,
exactly like double-clicking would with no arguments at all. If
iMolpro is already running, there is no running process for those
argv values to land in, so ``--args`` is silently dropped: nothing
happens. The mechanism that *does* reach an already-running app is
the standard macOS "open documents" Apple Event -- ``open -a Bundle
file...`` *without* ``--args`` -- which Launch Services delivers to
whichever instance is running (or a newly-started one, uniformly) and
which Qt already surfaces as a ``QEvent.Type.FileOpen`` event (see the
``App.event()`` override in ``__main__.main``, the same path used for
double-clicked project files). The catch is that Launch Services must
be able to resolve each argument to a real file: it cannot build a
document Apple Event for a path that doesn't exist yet.

That only matters in practice for a *new* ``.molpro`` project name
that hasn't been created yet -- ``iMolpro.py``'s own argument handling
otherwise creates the project directory itself once it receives the
path, and does so identically whether that directory started out
absent or empty (``Project(filename)`` on the Python side). So a
not-yet-existing ``*.molpro`` argument is pre-created here as an empty
directory stub before handing it to ``open``, letting it resolve like
any other file, while still leaving all the actual project
initialisation to iMolpro. Non-``.molpro`` arguments that don't exist
(e.g. a new, not-yet-written ``.inp`` file) are left to ``open``'s own
"no such file" error -- there is no empty stand-in that would make
sense to create on their behalf.

The command returns immediately rather than waiting for iMolpro to
quit -- there is nothing to wait for once the request has been handed
off to ``open``.

This is deliberately *not* done automatically as part of installation
(dragging the .app to /Applications, or mounting the DMG), because that
would mean writing outside /Applications without the user asking for
it. Instead it is offered as an explicit, user-triggered action from
the app's menu, invoked on demand and reversible.
"""
import os
import pathlib
import platform
import shlex
import subprocess
import sys
import tempfile

#: Where the wrapper script is installed. /usr/local/bin is the
#: conventional, already-on-$PATH location for locally-installed
#: command-line tools on macOS (the same directory Homebrew and the
#: Xcode command line tools use on Intel Macs, and still standard on
#: Apple Silicon).
TARGET_DIR = pathlib.Path('/usr/local/bin')
TARGET = TARGET_DIR / 'iMolpro'


def available() -> bool:
    """Whether installing a CLI command makes sense in this process.

    Only meaningful for the frozen macOS .app bundle: there is nothing
    to link to when running from a source checkout, and nothing to do
    on Windows or Linux, which already get a real ``iMolpro`` command
    from their own packaging (pip install / deb / rpm).
    """
    return platform.system() == 'Darwin' and hasattr(sys, '_MEIPASS')


def _app_executable() -> pathlib.Path:
    # For a PyInstaller --windowed macOS build, sys.executable *is*
    # Contents/MacOS/iMolpro -- the real native executable, not a
    # bootstrap wrapper.
    return pathlib.Path(sys.executable).resolve()


def _app_bundle() -> pathlib.Path:
    """The .app bundle directory containing the running executable."""
    for parent in _app_executable().parents:
        if parent.suffix == '.app':
            return parent
    raise RuntimeError('Could not locate the enclosing .app bundle.')


def _script_content(app_bundle: pathlib.Path) -> str:
    # No --args: see the module docstring for why plain document
    # arguments are required to reach an already-running instance, and
    # why a not-yet-existing *.molpro argument is stubbed out first.
    return (
        '#!/bin/sh\n'
        'for arg in "$@"; do\n'
        '  case "$arg" in\n'
        '    *.molpro) [ -e "$arg" ] || mkdir -p -- "$arg" ;;\n'
        '  esac\n'
        'done\n'
        f'exec /usr/bin/open -a {shlex.quote(str(app_bundle))} "$@"\n'
    )


def already_installed() -> bool:
    """Whether TARGET is our wrapper script for the running app."""
    try:
        if TARGET.is_symlink() or not TARGET.is_file():
            return False
        return TARGET.read_text() == _script_content(_app_bundle())
    except OSError:
        return False


def _run_privileged(shell_command: str) -> None:
    """Run shell_command via osascript, prompting for admin credentials.

    Raises RuntimeError with a human-readable message on failure or if
    the user cancels the authorisation dialog.
    """
    # Escape for embedding inside AppleScript's double-quoted string.
    escaped = shell_command.replace('\\', '\\\\').replace('"', '\\"')
    apple_script = f'do shell script "{escaped}" with administrator privileges'
    result = subprocess.run(['osascript', '-e', apple_script], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or 'Authorisation was cancelled.')


class ExistingFileConflict(RuntimeError):
    """Raised by install() when TARGET already exists, is not already
    our own wrapper script for the currently-running app, and
    ``overwrite=True`` was not passed."""


def _write_unprivileged(content: str) -> bool:
    """Try to (re)write TARGET without elevated privileges. Returns
    True on success, False if it needs an admin prompt instead."""
    try:
        TARGET_DIR.mkdir(parents=True, exist_ok=True)
        if TARGET.exists() or TARGET.is_symlink():
            TARGET.unlink()
        TARGET.write_text(content)
        TARGET.chmod(0o755)
        return True
    except OSError:
        return False


def _write_privileged(content: str) -> None:
    """(Re)write TARGET via a single osascript admin-privileges prompt.

    Removing any existing file and writing the new one are done as one
    combined shell command, so this only ever asks for the password
    once -- callers must not call this (or _run_privileged elsewhere)
    a second time as part of the same user-facing action, or the user
    would be prompted twice for what looks like a single operation.
    """
    fd, tmp_path = tempfile.mkstemp(prefix='iMolpro-cli-')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        os.chmod(tmp_path, 0o755)
        shell_command = (
            f'mkdir -p {shlex.quote(str(TARGET_DIR))} && '
            f'rm -f {shlex.quote(str(TARGET))} && '
            f'cp {shlex.quote(tmp_path)} {shlex.quote(str(TARGET))} && '
            f'chmod 755 {shlex.quote(str(TARGET))}'
        )
        _run_privileged(shell_command)
    finally:
        os.unlink(tmp_path)


def install(overwrite: bool = False) -> str:
    """Install /usr/local/bin/iMolpro as a wrapper around `open -a`.

    Tries an unprivileged write first (/usr/local/bin is sometimes
    already writable by the current user, e.g. if Homebrew has used it
    before), and only falls back to prompting for an admin password if
    that fails.

    If something already exists at TARGET that isn't our own wrapper
    script for the running app (e.g. a leftover from an older version
    of this feature, or something unrelated the user or another tool
    put there), it is left untouched and ExistingFileConflict is
    raised instead of being silently overwritten; pass
    ``overwrite=True`` (after asking the user) to replace it anyway.

    Returns a short human-readable status message. Raises RuntimeError
    if installation could not be completed.
    """
    if already_installed():
        return f"'iMolpro' is already installed at {TARGET}"

    if not overwrite and (TARGET.exists() or TARGET.is_symlink()):
        raise ExistingFileConflict(
            f'{TARGET} already exists and is not the iMolpro command line tool.')

    content = _script_content(_app_bundle())
    if not _write_unprivileged(content):
        _write_privileged(content)
    return f"Installed the 'iMolpro' command at {TARGET}"


def uninstall() -> str:
    """Remove the /usr/local/bin/iMolpro wrapper script, if present."""
    if not TARGET.exists() and not TARGET.is_symlink():
        return f"'iMolpro' command is not installed at {TARGET}"

    try:
        TARGET.unlink()
        return f"Removed the 'iMolpro' command from {TARGET}"
    except OSError:
        pass

    shell_command = f'rm -f {shlex.quote(str(TARGET))}'
    _run_privileged(shell_command)
    return f"Removed the 'iMolpro' command from {TARGET}"


def reinstall() -> str:
    """Force a fresh copy of the wrapper script into place, even if
    already_installed() is already True (e.g. to repair permissions,
    or simply as an explicit "yes, put a fresh copy there" action).

    Unlike install(), this always actually writes -- install() alone
    would just report "already installed" and do nothing in that case.
    Removing any previous file and writing the new one is done as a
    single operation (see _write_privileged), so this prompts for an
    admin password at most once, not once for a separate removal step
    and again for the install step.
    """
    content = _script_content(_app_bundle())
    if not _write_unprivileged(content):
        _write_privileged(content)
    return f"Replaced the 'iMolpro' command at {TARGET}"
