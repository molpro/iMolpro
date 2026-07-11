from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtCore import QUrl
import sys
import pathlib

class WebEnginePage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        if level != QWebEnginePage.JavaScriptConsoleMessageLevel.InfoMessageLevel and 'Synchronous XMLHttpRequest' not in message:
            print('javaScriptConsoleMessage', level, message, lineNumber, sourceID, file=sys.stderr)


class VOD(QWebEngineView):
    def __init__(self, html, directory=None, width=800, height=420, verbosity=0, title='structure'):
        if verbosity:
            print(html)
            open('test.html', 'w').write(html)
        super().__init__()
        self.directory_ = directory
        self.title = title
        self.page_ = WebEnginePage()
        self.setPage(self.page_)
        if self.directory_ is not None:
            self.page().profile().downloadRequested.connect(self._download_requested)
        self.setHtml(html, QUrl.fromLocalFile(str(pathlib.Path(__file__).resolve())))

        self.setMinimumSize(width, height)

    def _download_requested(self, item):
        import re
        if item.downloadFileName():
            item.setDownloadFileName(re.sub(r' \(\d+\)\.', r'.', item.downloadFileName()))
            item.setDownloadDirectory(self.directory_)
            item.accept()
