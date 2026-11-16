import errno
import os
import tempfile
import time
from pathlib import Path

import pytest
import soundfile as sf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from audio_recorder import AudioRecorder
from gui import SettingsWindow
from olympiad_window import OlympiadWindow, RecordingSettingsDialog, State


@pytest.fixture
def window(fake_sc, tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("folder", str(tmp_path / "recordings"))
    settings.setValue("format", "wav")
    widget = OlympiadWindow(settings)
    widget.show()
    yield widget
    if widget.recorder is not None:
        widget.recorder.stop()
        widget.recorder.join(10)
        app.processEvents()
    widget.close()


def wait_for(condition, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QApplication.instance().processEvents()
        if condition():
            return
        time.sleep(0.01)
    pytest.fail("Recording did not reach the expected state")


def start_with_audio(window):
    window.code.setText("00125")
    window.start_button.click()
    wait_for(lambda: window.recorder.recorders and window.recorder.recorders[0].frames > 0)


@pytest.mark.parametrize("output_format", ["wav", "mp3", "flac"])
def test_recording_states_and_exact_filename(window, output_format):
    window.output_format = output_format
    destination = window.output_folder / f"00125.{output_format}"
    assert window.state is State.READY
    assert not window.start_button.isEnabled()
    start_with_audio(window)
    assert window.filename.text() == f"Имя файла: {destination.name}"
    assert window.state is State.RECORDING
    assert not destination.exists()
    assert not window.code.isEnabled()
    assert not window.folder_button.isEnabled()
    assert not window.settings_button.isEnabled()

    recorder = window.recorder
    window.code.setText("00200")  # Even a programmatic edit cannot change the active filename.
    window.stop_button.click()
    assert window.state is State.SAVING
    assert not window.code.text()
    assert window.filename.text() == f"Имя файла: код_участника.{output_format}"
    assert not window.stop_button.isEnabled()
    assert not window.code.isEnabled()
    assert not window.start_button.isEnabled()
    window.stop_recording()
    window.start_recording()
    assert window.recorder is recorder
    wait_for(lambda: window.state is State.SAVED)

    assert window.code.isEnabled()
    assert window.settings_button.isEnabled()
    assert list(window.output_folder.iterdir()) == [destination]
    assert sf.info(destination).frames > 0
    assert window.recent.itemAt(0).widget().findChild(type(window.filename), "fileName").text() == destination.name


@pytest.mark.parametrize("code", ["../00125", "00125.wav", "COM1", "A" * 65])
def test_invalid_code_cannot_start(window, code):
    window.code.setText(code)
    window.start_button.click()
    assert window.state is State.ERROR
    assert window.recorder is None
    assert not window.output_folder.exists()


@pytest.mark.parametrize("late", [False, True])
def test_filename_collision_preserves_existing_recording(window, late):
    destination = window.output_folder / "00125.wav"
    window.output_folder.mkdir()
    if late:
        start_with_audio(window)
    destination.write_bytes(b"first recording")
    if late:
        window.stop_button.click()
    else:
        window.code.setText("00125")
        window.start_button.click()
    wait_for(lambda: window.state is State.ERROR)
    assert destination.read_bytes() == b"first recording"
    assert "уже существует" in window.status_detail.text()
    assert window.recorder is None
    if late:
        recovery, = window.output_folder.glob(".oly-00125-*.wav")
        assert str(recovery) in window.status_detail.text()
        assert sf.info(recovery).frames > 0


def test_write_failure_retains_raw_audio(window, tmp_path, monkeypatch):
    def fail(recorder, sources, path):
        Path(path).write_bytes(b"partial output")
        raise OSError(errno.ENOSPC, "disk full")

    monkeypatch.setattr(AudioRecorder, "_write_output", fail)
    start_with_audio(window)
    window.stop_button.click()
    wait_for(lambda: window.state is State.ERROR)
    assert not list(window.output_folder.iterdir())
    recovery, = tmp_path.glob("oly-00125-*.wav")
    assert sf.info(recovery).frames > 0
    assert str(recovery) in window.status_detail.text()
    assert "Недостаточно места" in window.status_detail.text()


def test_device_loss_reports_error_and_keeps_audio(window, fake_sc):
    fake_sc.mic.die_after = 4096
    start_with_audio(window)
    wait_for(lambda: window.state is State.ERROR)
    assert "Сохранено в 00125.wav" in window.status_detail.text()
    assert sf.info(window.output_folder / "00125.wav").frames == 4096


def test_closing_is_blocked_during_recording_and_saving(window):
    start_with_audio(window)
    assert not window.close()
    assert window.isVisible()
    assert window.state is State.RECORDING
    assert not window.recorder.stop_event.is_set()
    assert "Сначала нажмите «Стоп»" in window.status_detail.text()
    window.stop_button.click()
    assert not window.close()
    assert window.isVisible()
    assert window.state is State.SAVING
    wait_for(lambda: window.state is State.SAVED)
    assert sf.info(window.output_folder / "00125.wav").frames > 0
    assert window.isVisible()
    assert window.close()
    assert not window.isVisible()


def test_full_and_basic_settings_share_values(window, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    new_folder = tmp_path / "new recordings"

    def choose_basics(dialog):
        dialog.folder.setText(str(new_folder))
        dialog.output_format.setCurrentText("MP3")
        dialog.microphone.setCurrentIndex(dialog.microphone.findData("Fake Mic"))
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(RecordingSettingsDialog, "exec", choose_basics)
    basic, full = window.settings_button.menu().actions()
    basic.trigger()
    full.trigger()
    advanced = window.findChild(SettingsWindow)
    assert advanced.isVisible()
    assert advanced.lbl_folder.text() == str(new_folder)
    assert advanced.combo_fmt.currentText() == "MP3"
    assert advanced.combo_mic.currentData() == "Fake Mic"
    assert advanced.hk_both is not None
    assert advanced.chk_delete is not None

    advanced.combo_fmt.setCurrentText("WAV")
    advanced.chk_normalize.setChecked(True)
    advanced.chk_mono.setChecked(True)
    advanced.spin_auto_stop.setValue(1)
    advanced.save_settings()
    advanced.close()
    persisted = QSettings(window.settings.fileName(), QSettings.Format.IniFormat)
    assert persisted.value("full_settings")["normalize"] is True
    check = RecordingSettingsDialog(window)
    assert check.output_format.currentText() == "WAV"
    assert check.folder.text() == str(new_folder)

    start_with_audio(window)
    assert window.recorder.normalize and window.recorder.mono
    assert window.recorder.source_mode == "mic"
    assert window.auto_stop.isActive()
    assert window.auto_stop.interval() == 60_000
    window.stop_button.click()
    wait_for(lambda: window.state is State.SAVED)
    assert sf.info(new_folder / "00125.wav").channels == 1


def test_mp3_is_default_in_both_settings_dialogs(window):
    window.settings.remove("format")
    window.reload_settings()
    assert window.filename.text() == "Имя файла: код_участника.mp3"
    assert RecordingSettingsDialog(window).output_format.currentText() == "MP3"
    window.open_full_settings()
    advanced = window.findChild(SettingsWindow)
    try:
        assert advanced.combo_fmt.currentText() == "MP3"
    finally:
        advanced.close()


def test_folder_path_click_creates_and_opens_recordings_folder(window, monkeypatch):
    opened = []

    def open_url(url):
        folder = Path(url.toLocalFile())
        assert folder.is_dir()
        opened.append(folder)
        return True

    monkeypatch.setattr(QDesktopServices, "openUrl", open_url)
    assert not window.output_folder.exists()
    window.folder_button.click()
    assert opened == [window.output_folder]


def test_folder_path_click_reports_open_failure(window, monkeypatch):
    warnings = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: False)
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, detail: warnings.append(detail))
    window.folder_button.click()
    assert len(warnings) == 1
    assert str(window.output_folder) in warnings[0]


def test_global_hotkeys_use_participant_code_and_stop(window):
    window.code.setText("00125")
    window.hotkey.emit("loopback")
    wait_for(lambda: window.recorder is not None and window.recorder.recorders
             and window.recorder.recorders[0].frames > 0)
    assert window.recorder.source_mode == "loopback"
    window.hotkey.emit("stop")
    wait_for(lambda: window.state is State.SAVED)
    assert not window.code.text()
    assert (window.output_folder / "00125.wav").is_file()
