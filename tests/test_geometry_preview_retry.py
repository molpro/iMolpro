"""
Regression tests for the input-structure preview's retry behaviour.

ProjectWindow.initial_xyz_async() is called from a 1-second timer. A failed attempt leaves no xyz file,
so the preview stays "stale", and it used to launch Molpro again on every tick for as long as the
failure persisted (eg because Molpro did not report the geometry for the input), which in turn
exhausted the user's process table. A failed attempt must not be repeated until the input changes.

A real ProjectWindow needs Qt, VTK and a live project, so the real methods are bound to a small
stand-in object.
"""
import os
import types

import pytest

pytest.importorskip('iMolpro.ProjectWindow', reason='ProjectWindow needs a Qt binding and VTK',
                    exc_type=ImportError)
from iMolpro.ProjectWindow import ProjectWindow  # noqa: E402


class _Pane:
    def __init__(self, text):
        self.text = text

    def toPlainText(self):
        return self.text


class _SynchronousExecutor:
    def submit(self, function):
        function()


def _make_window(tmp_path, compute):
    """A stand-in for a ProjectWindow whose preview is permanently stale and whose Molpro run is `compute`"""
    import threading
    input_file = tmp_path / 'job.inp'
    input_file.write_text('geometry={he}\nhf\n')
    xyz_file = tmp_path / 'job.xyz'  # never created: that is what makes the preview stale

    window = types.SimpleNamespace(
        input_pane=_Pane('geometry={he}\nhf\n'),
        project=types.SimpleNamespace(filename=lambda *args, **kwargs: str(input_file)),
        geometry_files=lambda: [],
        thread_executor=_SynchronousExecutor(),
        _initial_xyz_lock=threading.Lock(),
        _initial_xyz_failed_key=None,
        _last_geometry_exception=None,
        launches=0,
    )

    def staleness():
        return True, str(xyz_file), 'he'

    def compute_initial_xyz(path):
        window.launches += 1
        return compute(window, path)

    window._initial_xyz_staleness = staleness
    window._compute_initial_xyz = compute_initial_xyz
    if hasattr(ProjectWindow, '_initial_xyz_input_key'):
        window._initial_xyz_input_key = types.MethodType(ProjectWindow._initial_xyz_input_key, window)
    window.initial_xyz_async = types.MethodType(ProjectWindow.initial_xyz_async, window)
    return window, input_file


def _failing_run(window, path):
    return ''  # Molpro ran but produced no geometry


def test_failed_preview_is_not_retried_while_input_is_unchanged(tmp_path):
    window, _ = _make_window(tmp_path, _failing_run)
    for _ in range(10):  # ten timer ticks
        window.initial_xyz_async()
    assert window.launches == 1


def test_exception_in_preview_is_not_retried_while_input_is_unchanged(tmp_path):
    def raising_run(window, path):
        raise RuntimeError('boom')

    window, _ = _make_window(tmp_path, raising_run)
    for _ in range(10):
        window.initial_xyz_async()
    assert window.launches == 1


def test_failed_preview_is_retried_after_the_input_text_changes(tmp_path):
    window, _ = _make_window(tmp_path, _failing_run)
    window.initial_xyz_async()
    window.initial_xyz_async()
    assert window.launches == 1
    window.input_pane.text = 'geometry={ne}\nhf\n'
    window.initial_xyz_async()
    assert window.launches == 2
    window.initial_xyz_async()
    assert window.launches == 2


def test_failed_preview_is_retried_after_the_input_file_changes(tmp_path):
    window, input_file = _make_window(tmp_path, _failing_run)
    window.initial_xyz_async()
    assert window.launches == 1
    input_file.write_text('geometry={he}\nhf\n! edited\n')
    os.utime(input_file, ns=(1, 1))  # guarantee a different modification time whatever the clock resolution
    window.initial_xyz_async()
    assert window.launches == 2


def test_successful_preview_clears_the_failure(tmp_path):
    results = iter(['', 'job.xyz'])
    window, _ = _make_window(tmp_path, lambda w, path: next(results))
    window.initial_xyz_async()
    assert window._initial_xyz_failed_key is not None
    window.input_pane.text = 'geometry={ne}\nhf\n'
    window.initial_xyz_async()
    assert window._initial_xyz_failed_key is None
