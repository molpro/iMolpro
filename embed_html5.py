from PyQt5 import QtWebChannel
from PyQt5.QtCore import QUrl, QResource
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView
import pathlib

class MyWindow(QWidget):
    def __init__(self):
        super().__init__()

        # Create a layout for the window
        layout = QVBoxLayout()


        webview = QWebEngineView()

        html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script type="text/javascript" src="JSmol.min.js"> </script>
</head>
<body>
<h2>Example of embedded JSmol</h2>
See <a href="https://wiki.jmol.org/index.php/Programmatic_Access_to_Jmol" target="_external">https://wiki.jmol.org/index.php/Programmatic_Access_to_Jmol</a>
<script>
var Info = {
  color: "#FFFFFF",
  height: 600,
  width: 600,
  script: "load malo.molden; mo 1; mo nomesh fill translucent 0.3; mo resolution 7; set antialiasDisplay ON",
  use: "HTML5",
  j2sPath: "j2s",
  serverURL: "php/jsmol.php",
};

Jmol.getApplet("myJmol", Info);
</script>

<script>
Jmol.script(myJmol, "mo HOMO");
</script>


<!--
<h2>Use JavaScript to Change Text</h2>
<p>This example writes "Hello JavaScript!" into an HTML element with id="demo":</p>

<p id="demo"></p>

<script>
document.getElementById("demo").innerHTML = "Hello JavaScript!";
</script>
-->

</body>
</html>"""
        cwd = str(pathlib.Path(__file__).resolve())
        webview.setHtml(html, QUrl.fromLocalFile(cwd))

        webview.setMinimumSize(800,900)
        layout.addWidget(webview)

        self.setLayout(layout)

if __name__ == '__main__':
    # Create the application
    app = QApplication([])

    # Create a window and show it
    window = MyWindow()
    window.show()

    # Run the event loop
    app.exec_()