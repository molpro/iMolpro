import os.path

from utilities import EditFile
import time


def ensure_trailing_newline(txt: str):
    return txt if txt and txt[-1] == '\n' else str(txt + '\n')


def test_content(qtbot, tmpdir):
    test_file = tmpdir / 'test-Editfile.txt'
    test_text = 'hello'
    with open(test_file, 'w') as f:
        f.write(test_text)
    editor = EditFile(test_file)
    qtbot.addWidget(editor)
    assert editor.toPlainText() == ensure_trailing_newline(test_text)

    for test_text in [
        '', ' ', 'one line', 'one line with newline\n', 'more\nlines', 'more\nlines\nwith\nnewline\n',
        'trailing space ',
        ' leading and trailing space with newline \n',
        'three newlines\n\n\n',
        'two newlines\n\n',
    ]:
        editor.setPlainText(test_text)
        assert editor.toPlainText() == ensure_trailing_newline(test_text)
        editor.sync()
        with open(test_file, 'r') as f:
            assert f.read() == ensure_trailing_newline(test_text)

        replacement_text = 'new stuff\n' + test_text
        from time import sleep
        sleep(0.1) # to give filesystem a chance to record different time
        with open(test_file, 'w') as f:
            f.write(replacement_text)
        file_written_time = os.path.getmtime(test_file)
        editor.sync()
        assert editor.toPlainText() == ensure_trailing_newline(replacement_text)
        assert os.path.getmtime(test_file) == file_written_time # editor should not have written unnecessarily
