# Разработка Olympiad Recorder

## Сборка и тесты на Windows 10 LTSC

Целевая конфигурация для этих шагов — Windows 10 LTSC x64 версии 1809 или новее и Python 3.12 x64. Qt 6.8 поддерживает эту версию Windows. [Qt for Windows](https://doc.qt.io/qt-6.8/windows.html)

В PowerShell из корня репозитория выполните:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install "PyQt6~=6.8.0" "PyQt6-Qt6~=6.8.0" soundcard sounddevice soundfile numpy lameenc keyboard pytest pyinstaller
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m PyInstaller --noconsole --onefile --noupx --name OlympiadRecorder main.py
.\dist\OlympiadRecorder.exe
```

Для запуска из исходников используйте `.\.venv\Scripts\python.exe main.py`. Для режима трея добавьте аргумент `--tray`. Автоматические тесты подменяют микрофон. Дополнительные проверки аудиотракта выполняются при наличии [VB-Audio Virtual Cable](https://vb-audio.com/Cable/).

На целевом компьютере запустите собранный EXE и:

1. Выберите рабочий микрофон и папку. Запишите с физического микрофона код `00125` в WAV, затем в MP3. Откройте оба файла и прослушайте их.
2. Повторите запуск с тем же кодом и форматом. Проверьте сообщение о конфликте и убедитесь, что первый файл сохранился.
3. Начните новую запись, отключите микрофон после нескольких секунд речи и проверьте сообщение об ошибке и сохранённый фрагмент.
4. Сверьте внешний вид с [макетами](ui-reference/) при рабочем масштабе экрана. Откройте оба диалога настроек и проверьте, что после перезапуска EXE видны сохранённые параметры.
5. Во время записи попробуйте закрыть окно крестиком и сочетанием `Alt+F4`. Убедитесь, что запись продолжается. Нажмите **Стоп**, проверьте пустое поле кода и дождитесь сохранения файла с исходным кодом. После этого окно должно закрываться обычным способом.

## CI и выпуск релиза

GitHub Actions запускает тесты и собирает EXE для Windows x64 и ARM64 при push в `master` и обновлении pull request. Сборки и файлы SHA-256 доступны в разделе **Artifacts** прогона **CI and release**. Этот прогон также можно запустить вручную.

Для выпуска отправьте тег `v*` с нужного коммита. Например, для версии `v0.1.0`:

```powershell
git tag -a v0.1.0 -m "Olympiad Recorder v0.1.0"
git push origin v0.1.0
```

После успешных тестов и сборки GitHub создаст черновик релиза с файлами `OlympiadRecorder.exe` для Windows x64, `OlympiadRecorder-arm64.exe` для Windows ARM64 и контрольными суммами. Проверьте вложения и опубликуйте черновик в **Releases**.
