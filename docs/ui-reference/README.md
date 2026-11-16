# Olympiad Recorder: UI reference for Codex

This package is a visual reference, **not** a sound-recording implementation. It faithfully recreates the compact window we agreed on in the earlier ChatGPT conversation.

## Files

- `01_ready.png`: main window in the ready-to-record state (primary visual reference).
- `02_recording.png`: the same window during recording.
- `03_saved.png`: the same window immediately after saving a recording.
- `prototype.html`: an interactive, local, no-dependency HTML mockup. Open in a browser; the buttons change mock states but do not record audio.

## Functional requirements

Build a native, always-visible PyQt6 window for Windows 10 LTSC, using the original QuickAudioRecorder recording engine as far as practical. The mockup is the visual target: compact single-column layout, input for participant code, proposed filename, prominent status panel, large Start/Stop buttons, recent recordings, and destination-folder line.

1. The operator enters a participant code, e.g. `00125`. Preserve leading zeroes and do not convert codes to integers.
2. On Start, validate the code, snapshot it as the active recording's immutable identifier, and begin recording using the existing recording backend. Disable editing the code until the recording has safely stopped.
3. On Stop, finish and persist audio to `<code>.<selected_format>` inside the configured output folder, e.g. `00125.wav`. WAV and MP3 should remain available if supported by the backend.
4. Never silently overwrite any existing recording; clearly notify the operator and provide a safe recovery path.
5. Clearly distinguish `Ready`, `Recording`, `Saving`, `Saved`, and `Error`. Do not show success before the file actually exists and has been finalized.
6. Disable controls appropriately to prevent overlapping recordings, accidental duplicate stops, or new recording while the prior file is still being saved.
7. Show the most recent files in the window, and keep the configured output path visible. Treat the illustrated path `D:\Olympiad\Audio` as an example, not a hard-coded default.
8. Surface microphone/device errors, insufficient disk space, and failed writes clearly. Do not discard an unsaved recording without explanation.
9. Prefer minimal changes to the stable audio engine. Keep the UX simple; avoid adding participant databases, playlists, or unnecessary settings to the main window.
10. Build and verify on the target Windows 10 LTSC machine. A cloud environment cannot test the physical microphone.

## Visual details

Approximate client width: 420 px; white card-style background, neutral grey status panel, deep blue Start button, neutral Stop button, restrained typography resembling Segoe UI, generous but compact spacing. The mockup has a pill reading `Макет` and a footer warning that it does not record audio; these are **prototype-only** labels and should be **removed** in the real application.

## Prompt to give Codex

> Use the attached `01_ready.png`, `02_recording.png` and `03_saved.png` as a faithful visual reference for the PyQt6 main window of the QuickAudioRecorder fork. Read `README.md` for behavior and safety requirements. First inspect the existing repository and propose the smallest set of changes needed. Preserve the existing audio-recording backend unless necessary, and implement filename generation from the operator-entered participant code. Don't overwrite files silently. Write tests for code preservation (including leading zeroes), filename collisions, and transitions among idle/recording/saving/saved/error. Finally document Windows 10 LTSC build and test steps.
