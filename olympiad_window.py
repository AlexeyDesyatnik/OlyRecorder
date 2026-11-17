import os
import re
import stat
from enum import Enum, auto
from pathlib import Path

from PyQt6.QtCore import QMimeData, QSettings, QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLayout, QLineEdit, QMenu, QMessageBox, QPushButton, QToolButton,
    QVBoxLayout, QWidget,
)

from audio_recorder import AudioRecorder, get_devices
from gui import (
    SHARED_KEYS, SettingsWindow, bind_hotkeys, default_recordings_folder, load_recording_settings,
)


FORMATS = ("wav", "mp3", "flac")
DEFAULT_FORMAT = "mp3"
CODE_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")
RESERVED_NAMES = re.compile(r"CON|PRN|AUX|NUL|(?:COM|LPT)[0-9]", re.IGNORECASE)

MIC = '<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v5m-4 0h8"/>'
RECORD = '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3" fill="currentColor" stroke="none"/>'
FOLDER = '<path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'
FILE = '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M9 15h6"/>'
CHECK = '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>'
PLAY = '<path fill="currentColor" stroke="none" d="M8 5.5c0-.8.85-1.3 1.55-.87l10.1 6.5a1.04 1.04 0 0 1 0 1.74l-10.1 6.5A1 1 0 0 1 8 18.5z"/>'
STOP = '<rect fill="currentColor" stroke="none" x="5" y="5" width="14" height="14" rx="2"/>'

STYLE = """
QWidget#card { background: white; border: 1px solid #e0e5eb; border-radius: 14px; }
QWidget#card * { font-family: 'Segoe UI'; color: #1d2734; }
QLabel#brand, QLabel#statusTitle { font-size: 17px; font-weight: 700; }
QLabel#codeLabel { color: #4e5b6b; font-size: 13px; font-weight: 600; }
QLineEdit {
    background: white; border: 1px solid #cfd7e1; border-radius: 9px;
    padding: 0 12px; font-size: 16px; selection-background-color: #2563ca;
}
QLineEdit:focus { border-color: #507fca; }
QWidget#card QLineEdit:disabled { background: #f7f9fb; color: #5d6a7a; }
QLabel#filename { color: #748092; font-size: 12px; }
QFrame#status { background: #f4f6f8; border-radius: 10px; }
QLabel#statusDetail { color: #7b8695; font-size: 12px; }
QPushButton#start, QPushButton#stop {
    border: 1px solid transparent; border-radius: 9px; font-size: 15px; font-weight: 700;
}
QWidget#card QPushButton#start { background: #2563ca; color: white; }
QWidget#card QPushButton#start:hover { background: #1e56b4; }
QWidget#card QPushButton#start:disabled { background: #92b1e5; }
QWidget#card QPushButton#stop { background: #e9edf2; color: #3b4655; }
QWidget#card QPushButton#stop:hover { background: #dce3ec; }
QWidget#card QPushButton#stop:disabled { background: #f4f6f8; color: #9da3ac; }
QPushButton#start:focus, QPushButton#stop:focus { border-color: #193e76; }
QFrame#separator { background: #e8ecf1; }
QLabel#recentTitle { font-size: 14px; font-weight: 700; }
QLabel#empty { font-size: 13px; color: #939ca9; }
QLabel#fileName { font-size: 13px; }
QWidget#card QPushButton#folder {
    background: transparent; border: 1px solid transparent; padding: 0;
    font-size: 12px; color: #7b8796;
}
QPushButton#folder:hover { text-decoration: underline; }
QPushButton#folder:focus { border-color: #cfd7e1; border-radius: 4px; }
QToolButton#settings {
    background: #f4f6f8; border: 1px solid #e0e5eb; border-radius: 5px;
    padding: 3px 17px 3px 7px; font-size: 12px;
}
QToolButton#settings:hover, QToolButton#settings:focus { border-color: #507fca; }
QToolButton#settings::menu-indicator {
    subcontrol-origin: padding; subcontrol-position: right center; right: 5px;
}
QWidget#card QToolButton#settings:disabled { color: #9da3ac; }
"""


class State(Enum):
    READY = auto()
    RECORDING = auto()
    SAVING = auto()
    SAVED = auto()
    ERROR = auto()


def icon_pixmap(drawing, size, color="#68768a", dpr=1.0):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{drawing}</svg>'
    renderer = QSvgRenderer(svg.replace("currentColor", color).encode())
    pixels = round(size * dpr)
    pixmap = QPixmap(pixels, pixels)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


class RecordingSettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Настройки записи")
        layout = QFormLayout(self)

        self.microphone = QComboBox()
        self.microphone.addItem("Микрофон Windows по умолчанию", "")
        for device in get_devices():
            self.microphone.addItem(device["name"], device["id"])
        if parent.microphone_id:
            index = self.microphone.findData(parent.microphone_id)
            if index == -1:
                self.microphone.addItem("Выбранный микрофон недоступен", parent.microphone_id)
                index = self.microphone.count() - 1
            self.microphone.setCurrentIndex(index)
        layout.addRow("Микрофон", self.microphone)

        self.output_format = QComboBox()
        self.output_format.addItems([fmt.upper() for fmt in FORMATS])
        self.output_format.setCurrentText(parent.output_format.upper())
        layout.addRow("Формат", self.output_format)

        self.folder = QLineEdit(str(parent.output_folder))
        self.folder.setReadOnly(True)
        browse = QPushButton("Обзор…")
        browse.clicked.connect(self.browse)
        row = QHBoxLayout()
        row.addWidget(self.folder, 1)
        row.addWidget(browse)
        layout.addRow("Папка", row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.setMinimumWidth(440)

    def browse(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Папка для записей", self.folder.text(),
            options=QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontUseNativeDialog,
        )
        if folder:
            self.folder.setText(str(Path(folder)))


class OlympiadWindow(QWidget):
    finished = pyqtSignal(str, str)
    progress = pyqtSignal(float)
    interrupted = pyqtSignal(str)
    hotkey = pyqtSignal(str)

    def __init__(self, settings=None):
        super().__init__()
        self.setWindowTitle("Olympiad Recorder")
        self.setWindowIcon(QIcon(icon_pixmap(MIC, 32, dpr=self.devicePixelRatioF())))
        self.settings = settings if settings is not None else app_settings()
        self.recorder = None
        self.state = State.READY
        self.saving_detail = ""
        self.hotkey_removers = []
        self.auto_stop = QTimer(self)
        self.auto_stop.setSingleShot(True)
        self.auto_stop.timeout.connect(self.stop_recording)

        self.build_ui()
        self.finished.connect(self.on_finished, Qt.ConnectionType.QueuedConnection)
        self.progress.connect(self.on_progress, Qt.ConnectionType.QueuedConnection)
        self.interrupted.connect(self.on_interrupted, Qt.ConnectionType.QueuedConnection)
        self.hotkey.connect(self.on_hotkey, Qt.ConnectionType.QueuedConnection)
        self.reload_settings()
        self.code.setFocus()

    def build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
        card = QFrame(objectName="card")
        card.setFixedWidth(420)
        card.setStyleSheet(STYLE)
        outer.addWidget(card)
        column = QVBoxLayout(card)
        column.setContentsMargins(19, 19, 19, 19)
        column.setSpacing(0)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        brand.addWidget(self.icon_label(MIC, 20))
        brand_label = QLabel("Olympiad Recorder", objectName="brand")
        brand_label.setFixedHeight(24)
        brand.addWidget(brand_label)
        brand.addStretch()
        self.settings_button = QToolButton(objectName="settings")
        self.settings_button.setText("Настройки")
        self.settings_button.setFixedHeight(24)
        self.settings_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        settings_menu = QMenu(self.settings_button)
        settings_menu.addAction("Основные настройки…", self.open_settings)
        settings_menu.addAction("Все настройки…", self.open_full_settings)
        self.settings_button.setMenu(settings_menu)
        brand.addWidget(self.settings_button)
        column.addLayout(brand)
        column.addSpacing(23)

        code_label = QLabel("Код участника", objectName="codeLabel")
        code_label.setFixedHeight(15)
        self.code = QLineEdit()
        self.code.setAccessibleName(code_label.text())
        self.code.setPlaceholderText("Например, 00125")
        self.code.setFixedHeight(44)
        self.code.textChanged.connect(self.on_code_changed)
        self.code.returnPressed.connect(self.start_recording)
        column.addWidget(code_label)
        column.addSpacing(8)
        column.addWidget(self.code)
        column.addSpacing(9)
        self.filename = QLabel(objectName="filename")
        self.filename.setFixedSize(380, 14)
        self.filename.setTextFormat(Qt.TextFormat.PlainText)
        column.addWidget(self.filename)
        column.addSpacing(19)

        panel = QFrame(objectName="status")
        panel.setMinimumHeight(110)
        status = QVBoxLayout(panel)
        status.setContentsMargins(12, 17, 12, 17)
        status.setSpacing(8)
        status.addStretch()
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_row.addStretch()
        self.status_icon = self.icon_label(MIC, 20)
        self.status_title = QLabel(objectName="statusTitle")
        title_row.addWidget(self.status_icon)
        title_row.addWidget(self.status_title)
        title_row.addStretch()
        status.addLayout(title_row)
        self.status_detail = QLabel(objectName="statusDetail")
        self.status_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_detail.setTextFormat(Qt.TextFormat.PlainText)
        self.status_detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.status_detail.setWordWrap(True)
        status.addWidget(self.status_detail)
        status.addStretch()
        column.addWidget(panel)
        column.addSpacing(15)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.start_button = QPushButton("Начать", objectName="start")
        self.stop_button = QPushButton("Стоп", objectName="stop")
        for button in (self.start_button, self.stop_button):
            button.setFixedHeight(47)
            button.setIconSize(QSize(16, 16))
            buttons.addWidget(button, 1)
        self.start_button.clicked.connect(lambda: self.start_recording())
        self.stop_button.clicked.connect(self.stop_recording)
        column.addLayout(buttons)
        column.addSpacing(20)
        separator = QFrame(objectName="separator")
        separator.setFixedHeight(1)
        column.addWidget(separator)
        column.addSpacing(17)
        column.addWidget(QLabel("Последние записи", objectName="recentTitle"))
        column.addSpacing(12)
        self.recent = QVBoxLayout()
        self.recent.setSpacing(0)
        column.addLayout(self.recent)
        column.addSpacing(21)

        self.folder_button = QPushButton(objectName="folder")
        self.folder_button.setAccessibleName("Открыть папку с записями")
        self.folder_button.setIcon(QIcon(icon_pixmap(FOLDER, 15, "#7b8796", self.devicePixelRatioF())))
        self.folder_button.setIconSize(QSize(15, 15))
        self.folder_button.setFixedHeight(20)
        self.folder_button.clicked.connect(self.open_output_folder)
        column.addWidget(self.folder_button)
        self.settings_shortcut = QShortcut(QKeySequence("Ctrl+,"), self)
        self.settings_shortcut.activated.connect(self.open_settings)

    def icon_label(self, drawing, size, color="#68768a"):
        label = QLabel()
        label.setPixmap(icon_pixmap(drawing, size, color, self.devicePixelRatioF()))
        label.setFixedSize(size, size)
        return label

    def open_settings(self):
        if self.recorder is not None:
            return
        dialog = RecordingSettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            values = {
                "output_folder": dialog.folder.text(),
                "format": dialog.output_format.currentText().lower(),
                "device_id": dialog.microphone.currentData(),
            }
            for key, value in values.items():
                self.settings.setValue(SHARED_KEYS[key], value)
            self.settings.sync()
            self.reload_settings()
            if self.settings.status() != QSettings.Status.NoError:
                self.set_state(State.ERROR, "Настройки действуют до выхода. Сохранить их не удалось.")
        dialog.deleteLater()

    def open_full_settings(self):
        if self.recorder is not None:
            return
        window = SettingsWindow(self, settings=self.settings, defaults={
            "format": DEFAULT_FORMAT,
        })
        window.setWindowModality(Qt.WindowModality.WindowModal)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window.settings_saved.connect(self.reload_settings)
        window.show()

    def reload_settings(self):
        self.preferences = load_recording_settings(self.settings)
        folder = self.preferences.get("output_folder")
        self.output_folder = Path(folder) if folder else default_recordings_folder()
        self.output_format = (self.preferences.get("format") or "").lower()
        if self.output_format not in FORMATS:
            self.output_format = DEFAULT_FORMAT
        self.microphone_id = self.preferences.get("device_id")
        self.unregister_hotkeys()
        self.hotkey_removers = bind_hotkeys(self.preferences, self.hotkey.emit)
        self.refresh_folder()
        self.set_ready()

    def unregister_hotkeys(self):
        for remove in self.hotkey_removers:
            remove()
        self.hotkey_removers.clear()

    def on_hotkey(self, mode):
        if QApplication.activeModalWidget() is not None or self.state is State.SAVING:
            return
        if mode == "stop" or self.state is State.RECORDING:
            self.stop_recording()
        else:
            self.start_recording(mode)

    def refresh_folder(self):
        path = str(self.output_folder)
        abbreviated = self.folder_button.fontMetrics().elidedText(path, Qt.TextElideMode.ElideMiddle, 340)
        self.folder_button.setText(abbreviated)
        self.folder_button.setToolTip(f"{path}\nОткрыть папку в Проводнике")
        self.refresh_recent()

    def open_output_folder(self):
        try:
            folder = self.output_folder.absolute()
            folder.mkdir(parents=True, exist_ok=True)
            if QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))):
                return
            detail = "Windows не удалось открыть папку в Проводнике."
        except OSError as exc:
            detail = str(exc)
        QMessageBox.warning(self, "Не удалось открыть папку", f"{self.output_folder}\n\n{detail}")

    def refresh_recent(self):
        while self.recent.count():
            widget = self.recent.takeAt(0).widget()
            widget.hide()
            widget.deleteLater()

        files = []
        try:
            for path in self.output_folder.iterdir():
                if path.suffix.lower()[1:] in FORMATS and not path.name.startswith(".oly-"):
                    try:
                        info = path.stat()
                    except OSError:
                        continue
                    if stat.S_ISREG(info.st_mode) and info.st_size:
                        files.append((info.st_mtime_ns, path.name))
        except OSError:
            pass  # The folder may not exist yet, or may be on a disconnected drive.

        if not files:
            empty = QLabel("Записей пока нет", objectName="empty")
            empty.setFixedHeight(18)
            self.recent.addWidget(empty)
        for _, name in sorted(files, reverse=True)[:3]:
            row = QWidget()
            row.setFixedHeight(33)
            layout = QHBoxLayout(row)
            layout.setSpacing(9)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.icon_label(FILE, 17, "#6e7888"))
            name_label = QLabel(row, objectName="fileName")
            name_label.setTextFormat(Qt.TextFormat.PlainText)
            name_label.setText(name_label.fontMetrics().elidedText(name, Qt.TextElideMode.ElideMiddle, 315))
            name_label.setToolTip(name)
            layout.addWidget(name_label, 1)
            layout.addWidget(self.icon_label(CHECK, 17, "#20825b"))
            self.recent.addWidget(row)

    def on_code_changed(self):
        if self.recorder is None:
            self.set_ready()
        else:
            self.update_filename()

    def update_filename(self):
        code = self.code.text().strip()
        stem = code if CODE_PATTERN.fullmatch(code) else "код_участника"
        preview = f"Имя файла: {stem}.{self.output_format}"
        self.filename.setText(self.filename.fontMetrics().elidedText(preview, Qt.TextElideMode.ElideMiddle, 380))
        self.filename.setToolTip(preview)

    def set_ready(self):
        self.update_filename()
        self.set_state(State.READY, "Введите код участника и начните запись")

    def set_state(self, state, detail):
        self.state = state
        title = {
            State.READY: "Готово к записи",
            State.RECORDING: "Идёт запись",
            State.SAVING: "Сохранение записи",
            State.SAVED: "Запись сохранена",
            State.ERROR: "Ошибка",
        }[state]
        self.status_title.setText(title)
        self.status_detail.setText(detail)
        self.status_detail.setFixedHeight(self.status_detail.heightForWidth(356))
        drawing = RECORD if state is State.RECORDING else MIC
        color = "#dc4747" if state in (State.RECORDING, State.ERROR) else "#68768a"
        dpr = self.devicePixelRatioF()
        self.status_icon.setPixmap(icon_pixmap(drawing, 20, color, dpr))
        busy = state in (State.RECORDING, State.SAVING)
        self.code.setEnabled(not busy)
        self.start_button.setEnabled(not busy and bool(self.code.text().strip()))
        self.stop_button.setEnabled(state is State.RECORDING)
        self.folder_button.setEnabled(not busy)
        self.settings_button.setEnabled(not busy)
        self.start_button.setIcon(QIcon(icon_pixmap(PLAY, 16, "white", dpr)))
        stop_color = "#3b4655" if self.stop_button.isEnabled() else "#9da3ac"
        self.stop_button.setIcon(QIcon(icon_pixmap(STOP, 16, stop_color, dpr)))

    def start_recording(self, mode="mic"):
        if self.recorder is not None or QApplication.activeModalWidget() is not None:
            return
        code = self.code.text().strip()
        if not CODE_PATTERN.fullmatch(code) or RESERVED_NAMES.fullmatch(code):
            self.set_state(State.ERROR, "Введите до 64 латинских букв, цифр, дефисов или знаков подчёркивания. "
                           "Системные имена Windows, например CON и COM1, недопустимы.")
            return
        filename = f"{code}.{self.output_format}"
        if os.path.lexists(self.output_folder / filename):
            self.set_state(State.ERROR, f"Файл {filename} уже существует. Выберите другой код или папку.")
            return

        self.saving_detail = f"Участник: {code}"
        self.recorder = AudioRecorder(
            mic_id=self.microphone_id or None, source_mode=mode,
            output_folder=str(self.output_folder), output_format=self.output_format,
            mono=self.preferences.get("mono", False),
            normalize=self.preferences.get("normalize", False),
            filename_stem=code,
            on_finish_callback=lambda path, error: self.finished.emit(path or "", error or ""),
            on_progress=self.progress.emit, on_notice=self.interrupted.emit,
        )
        self.set_state(State.RECORDING, self.saving_detail)
        try:
            self.recorder.start()
            limit = self.preferences.get("auto_stop_min", 0)
            if limit:
                self.auto_stop.start(limit * 60_000)
        except RuntimeError as error:
            self.on_finished("", str(error))

    def stop_recording(self):
        if self.state is State.RECORDING:
            self.auto_stop.stop()
            self.set_state(State.SAVING, self.saving_detail)
            self.code.clear()
            self.recorder.stop()

    def on_interrupted(self, _message):
        self.auto_stop.stop()
        self.saving_detail = "Запись прервалась. Сохраняется записанный звук."
        self.set_state(State.SAVING, self.saving_detail)

    def on_progress(self, fraction):
        if self.state is State.SAVING:
            self.status_detail.setText(f"{self.saving_detail} · {int(fraction * 100)}%")

    def on_finished(self, path, error):
        self.auto_stop.stop()
        self.recorder = None
        self.refresh_recent()
        self.update_filename()
        try:
            finalized = bool(path) and Path(path).is_file()
        except OSError as exc:
            finalized = False
            error = f"{error}\n{exc}".strip()
        if finalized:
            name = Path(path).name
            if self.preferences.get("clipboard"):
                data = QMimeData()
                data.setUrls([QUrl.fromLocalFile(path)])
                QApplication.clipboard().setMimeData(data)
            if error:
                self.set_state(State.ERROR, f"Запись прервалась. Сохранено в {name}.\n{error}")
            else:
                self.set_state(State.SAVED, f"Файл сохранён: {name}")
        else:
            if path:
                error = f"Итоговый файл недоступен: {path}\n{error}".rstrip()
            self.set_state(State.ERROR, f"Не удалось сохранить запись.\n{error}".rstrip())
        self.code.setFocus()

    def closeEvent(self, event):
        if self.recorder is not None:
            event.ignore()
            if self.state is State.RECORDING:
                self.set_state(State.RECORDING, f"{self.saving_detail}\nСначала нажмите «Стоп».")
        else:
            self.unregister_hotkeys()
            event.accept()


def app_settings():
    return QSettings("Olympiad Recorder", "Olympiad Recorder")
