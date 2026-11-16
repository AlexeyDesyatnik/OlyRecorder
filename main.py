import sys
from PyQt6.QtWidgets import QApplication
from olympiad_window import OlympiadWindow, app_settings


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Olympiad Recorder")
    if "--tray" in sys.argv:
        from gui import TrayApplication

        app.setQuitOnLastWindowClosed(False)
        tray = TrayApplication(app, settings=app_settings())
    else:
        window = OlympiadWindow()
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
