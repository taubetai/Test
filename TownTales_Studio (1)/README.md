# TownTales Studio — standalone procedural prototype

This replacement is **not the previous Work repository**: those files were unavailable. It creates new Blender renders for every job and uses a local Ollama story planner and your own Voice J WAV. It is a starting implementation, not a validated recreation of your reference videos. The procedural library has limited actions and geometry, and unsupported custom props become simple boxes. No sound effects or music are included yet. Revisions regenerate the entire film. Word alignment is approximate; pause adjustment only adds silence in safe detected gaps and cannot guarantee all requested pause lengths. Final tempo normalization may change those gaps. Rendering may take significant time.

## Local Mac setup
1. Extract ZIP to a new folder, not over your old TownTalesStudio. Open Terminal in the extracted folder.
2. Install Blender 4.2+ (https://www.blender.org/download/), Ollama (https://ollama.com/) and FFmpeg with libass (e.g. `brew install ffmpeg` if Homebrew is installed). Verify `ffmpeg -filters | grep ass`.
3. Open Ollama, then run `ollama pull qwen2.5:7b`.
4. Use your existing Python environment: `source ~/TownTalesStudio/.venv/bin/activate` then `uv pip install mlx-whisper`.
5. Verify `~/TownTalesStudio/narrators/voice_J*.wav` contains the original Voice J recording. The exact filename must be `voice_J.wav` or start with `voice_J_`. Set `TOWNTALES_VOICE_ROOT` if you moved the file. Do not use J2/J3 as the reference.
6. Run `python engine.py` from the extracted folder and open http://127.0.0.1:8765. Start with 15 seconds and Preview quality. First run downloads the local Whisper model. Keep Ollama running.

## GitHub Pages
Upload the extracted files at the repository root (do not upload your local jobs, narration samples, models or virtual environment). Go to Settings > Pages > Deploy from a branch > main > /(root). The root `index.html` is the frontend. Start your local backend with `TOWNTALES_PAGES_ORIGIN=https://YOUR-USERNAME.github.io python engine.py`. Set the engine address in the web interface to `http://127.0.0.1:8765`. Browsers may block a hosted HTTPS site's request to a local HTTP service or require local network permission; if blocked use the local website instead. Pages cannot run Blender, Qwen, or Python itself. The local backend is intentionally bound to localhost, not a public service.

## Settings
Voice J reference from previous tests, Qwen Base 5-bit, initial 0.90 tempo, 125ms comma / 300ms sentence / 450ms ellipsis target. Fresh shots are aligned to narration; selectable 15–120 seconds; full export 1080x1920 30 fps, preview 540x960. If narration is too far from the requested time or visibly incomplete the job fails instead of knowingly exporting a cut-off story. Original script and ASS captions included. Jobs are stored locally in `jobs/`; restart loses in-memory job state but files remain. Never expose this development server to the internet.
