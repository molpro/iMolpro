import importlib
import os
import pathlib
import sys

import pytest


@pytest.fixture
def cli_install(tmp_path, monkeypatch):
    """Import cli_install with TARGET_DIR/TARGET redirected into tmp_path,
    and sys.executable/_MEIPASS faked to simulate the frozen macOS app."""
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
    module = importlib.import_module('iMolpro.cli_install')
    importlib.reload(module)

    fake_app_exe = tmp_path / 'iMolpro.app' / 'Contents' / 'MacOS' / 'iMolpro'
    fake_app_exe.parent.mkdir(parents=True)
    fake_app_exe.write_text('#!/bin/sh\necho fake\n')
    fake_app_exe.chmod(0o755)

    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
    monkeypatch.setattr(module.sys, 'executable', str(fake_app_exe))
    monkeypatch.setattr(module.platform, 'system', lambda: 'Darwin')

    fake_target_dir = tmp_path / 'bin'
    monkeypatch.setattr(module, 'TARGET_DIR', fake_target_dir)
    monkeypatch.setattr(module, 'TARGET', fake_target_dir / 'iMolpro')

    yield module


def test_available_true_when_frozen_darwin(cli_install):
    assert cli_install.available() is True


def test_available_false_when_not_darwin(cli_install, monkeypatch):
    monkeypatch.setattr(cli_install.platform, 'system', lambda: 'Linux')
    assert cli_install.available() is False


def test_available_false_when_not_frozen(cli_install, monkeypatch):
    monkeypatch.delattr(sys, '_MEIPASS', raising=False)
    assert cli_install.available() is False


def test_app_bundle_resolves_to_dot_app_directory(cli_install):
    bundle = cli_install._app_bundle()
    assert bundle.suffix == '.app'
    assert bundle.name == 'iMolpro.app'


def test_install_creates_open_wrapper_script(cli_install):
    assert not cli_install.already_installed()
    message = cli_install.install()
    assert str(cli_install.TARGET) in message

    assert cli_install.TARGET.is_file()
    assert not cli_install.TARGET.is_symlink()
    assert os.access(cli_install.TARGET, os.X_OK)

    content = cli_install.TARGET.read_text()
    assert content.startswith('#!/bin/sh')
    assert '/usr/bin/open' in content
    assert '-a' in content
    assert str(cli_install._app_bundle()) in content
    # Arguments must be passed as plain document paths (no --args), or
    # they are silently dropped when iMolpro is already running.
    assert '--args' not in content
    assert 'open -a' in content and '"$@"' in content
    # A not-yet-existing *.molpro argument must be pre-created so that
    # `open` can resolve it as a document.
    assert '*.molpro' in content
    assert 'mkdir' in content

    assert cli_install.already_installed()


def test_install_is_idempotent(cli_install):
    cli_install.install()
    message = cli_install.install()
    assert 'already installed' in message


def test_uninstall_removes_script(cli_install):
    cli_install.install()
    message = cli_install.uninstall()
    assert not cli_install.TARGET.exists()
    assert not cli_install.TARGET.is_symlink()
    assert 'Removed' in message


def test_uninstall_when_not_installed(cli_install):
    message = cli_install.uninstall()
    assert 'not installed' in message


def test_install_replaces_stale_symlink(cli_install, tmp_path):
    # Simulate a leftover symlink from an earlier version of this
    # feature (which installed a direct symlink rather than a wrapper
    # script). It's not our current script, so install() should treat
    # it like any other pre-existing file: raise a conflict rather
    # than silently clobbering it, and only replace it once told to
    # overwrite.
    cli_install.TARGET_DIR.mkdir(parents=True, exist_ok=True)
    stale = tmp_path / 'stale-executable'
    stale.write_text('old')
    cli_install.TARGET.symlink_to(stale)

    assert not cli_install.already_installed()
    with pytest.raises(cli_install.ExistingFileConflict):
        cli_install.install()
    assert cli_install.TARGET.is_symlink()  # untouched

    cli_install.install(overwrite=True)
    assert cli_install.TARGET.is_file()
    assert not cli_install.TARGET.is_symlink()
    assert cli_install.already_installed()


def test_install_raises_conflict_for_unrelated_existing_file(cli_install):
    # Something else entirely -- not ours, not a symlink -- already
    # sitting at TARGET must not be silently overwritten.
    cli_install.TARGET_DIR.mkdir(parents=True, exist_ok=True)
    cli_install.TARGET.write_text('#!/bin/sh\necho "not iMolpro at all"\n')
    cli_install.TARGET.chmod(0o755)

    with pytest.raises(cli_install.ExistingFileConflict):
        cli_install.install()
    assert cli_install.TARGET.read_text() == '#!/bin/sh\necho "not iMolpro at all"\n'


def test_install_overwrite_replaces_unrelated_existing_file(cli_install):
    cli_install.TARGET_DIR.mkdir(parents=True, exist_ok=True)
    cli_install.TARGET.write_text('#!/bin/sh\necho "not iMolpro at all"\n')
    cli_install.TARGET.chmod(0o755)

    message = cli_install.install(overwrite=True)
    assert str(cli_install.TARGET) in message
    assert cli_install.already_installed()


def test_install_does_not_raise_conflict_when_no_file_exists(cli_install):
    # Sanity check: overwrite=False (the default) must not itself
    # block a completely fresh install.
    assert not cli_install.TARGET.exists()
    cli_install.install()  # should not raise
    assert cli_install.already_installed()


def test_reinstall_replaces_even_when_already_correctly_installed(cli_install):
    cli_install.install()
    assert cli_install.already_installed()

    message = cli_install.reinstall()
    assert 'Replaced' in message
    assert str(cli_install.TARGET) in message
    assert cli_install.already_installed()


def test_reinstall_replaces_unrelated_existing_file(cli_install):
    cli_install.TARGET_DIR.mkdir(parents=True, exist_ok=True)
    cli_install.TARGET.write_text('#!/bin/sh\necho "not iMolpro at all"\n')
    cli_install.TARGET.chmod(0o755)

    message = cli_install.reinstall()
    assert 'Replaced' in message
    assert cli_install.already_installed()


def test_reinstall_works_when_nothing_installed_yet(cli_install):
    assert not cli_install.TARGET.exists()
    message = cli_install.reinstall()
    assert 'Replaced' in message
    assert cli_install.already_installed()


def test_reinstall_prompts_for_privileges_at_most_once(cli_install, monkeypatch):
    # Regression test: reinstall() used to be implemented as a plain
    # uninstall() followed by install(overwrite=True), each of which
    # falls back to its own separate osascript admin prompt -- so a
    # single "Reinstall" click could ask for the password twice. It
    # must now do at most one combined privileged write.
    calls = []
    monkeypatch.setattr(cli_install, '_write_unprivileged', lambda content: False)
    monkeypatch.setattr(cli_install, '_run_privileged', lambda shell_command: calls.append(shell_command))

    # Pre-existing install, to also exercise the "already installed"
    # case going through the same single-prompt path.
    cli_install.TARGET_DIR.mkdir(parents=True, exist_ok=True)
    cli_install.TARGET.write_text('stale content')

    cli_install.reinstall()
    assert len(calls) == 1


def test_install_prompts_for_privileges_at_most_once(cli_install, monkeypatch):
    calls = []
    monkeypatch.setattr(cli_install, '_write_unprivileged', lambda content: False)
    monkeypatch.setattr(cli_install, '_run_privileged', lambda shell_command: calls.append(shell_command))

    cli_install.install()
    assert len(calls) == 1


def test_already_installed_false_for_different_app_bundle(cli_install, tmp_path):
    # A script referencing some other/older app bundle location should
    # not be mistaken for a valid, current installation.
    cli_install.TARGET_DIR.mkdir(parents=True, exist_ok=True)
    cli_install.TARGET.write_text('#!/bin/sh\nexec /usr/bin/open -a /somewhere/else.app --args "$@"\n')
    cli_install.TARGET.chmod(0o755)
    assert not cli_install.already_installed()


def test_script_creates_stub_for_new_molpro_project_and_forwards_args(cli_install, tmp_path):
    """Exercise the generated shell script itself (not open, which
    isn't meaningfully testable here): a fake stand-in for
    /usr/bin/open echoes back whatever arguments it was actually
    given, so we can check that a not-yet-existing *.molpro argument
    is (a) pre-created as a directory and (b) still passed straight
    through as a plain document argument, with no --args flag."""
    import os as os_module
    import subprocess

    cli_install.install()
    script = cli_install.TARGET.read_text()

    fake_bin = tmp_path / 'fakebin'
    fake_bin.mkdir()
    fake_open = fake_bin / 'open'
    fake_open.write_text('#!/bin/sh\necho "OPEN_CALLED:$@"\n')
    fake_open.chmod(0o755)

    # Swap the hard-coded /usr/bin/open for our fake one on PATH,
    # keeping everything else (the mkdir loop, -a bundle, "$@") exactly
    # as iMolpro generates it.
    patched_script = script.replace('/usr/bin/open', 'open')
    script_file = tmp_path / 'iMolpro-under-test.sh'
    script_file.write_text(patched_script)
    script_file.chmod(0o755)

    new_project = tmp_path / 'brand-new.molpro'
    existing_input = tmp_path / 'existing.inp'
    existing_input.write_text('geometry')
    assert not new_project.exists()

    env = dict(os_module.environ)
    env['PATH'] = str(fake_bin) + ':' + env.get('PATH', '')

    result = subprocess.run(
        [str(script_file), str(new_project), str(existing_input)],
        capture_output=True, text=True, env=env,
    )

    assert result.returncode == 0, result.stderr
    assert new_project.is_dir()  # stub created so `open` can resolve it
    assert 'OPEN_CALLED' in result.stdout
    assert str(new_project) in result.stdout
    assert str(existing_input) in result.stdout
    assert '--args' not in result.stdout
