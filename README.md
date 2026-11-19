# Hajime

A small desktop app: a to-do list that earns Judo belts, plus a 25/5 Pomodoro timer.
Built with Python and [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter).

## Run

Requires Python 3.10+ with Tkinter.

```sh
pip install .           # installs CustomTkinter, adds the `hajime` command
hajime                  # or: python -m hajime
```

Windows: double-click `start.bat`. Optional crisper belt art: `pip install ".[svg]"`.

## Features

- Boards (Study, Finance, Judo...), each with its own tasks and belt. Add with
  **+ Board**; double-click to rename, right-click to delete.
- Add, check off, edit (click), drag to reorder and delete tasks.
- Seven belts, from white to black, unlocked as you finish tasks.
- Work/break timer (25/5) with a switch to jump between modes; tracks today's focus time.

Data is stored per user (`%APPDATA%\Hajime`, `~/Library/Application Support/Hajime`
or `~/.local/share/Hajime`); set `HAJIME_DATA_FILE` to use another file.
Unexpected errors are logged to `hajime.log` in the same folder.

Prebuilt Windows, macOS and Linux apps are attached to each
[GitHub release](../../releases).

## Development

```sh
pip install -e ".[dev]"
ruff check . && pytest      # GUI tests need a display (xvfb on Linux)
```

Pushing a `v*` tag builds the executables and attaches them to a release; bump
`__version__` in `hajime/__init__.py` first.

```text
hajime/
  models.py      Tasks, boards, belt ranks, Pomodoro state machine (no GUI)
  storage.py     JSON persistence and data location
  app.py         CustomTkinter UI
  belt_art.py    SVG belt rendering
  config.py      Belts, timer lengths, theme
packaging/       Launcher used for frozen builds
tests/           pytest suite
```

## License

Code: MIT ([LICENSE](LICENSE)).

Belt illustrations in `hajime/assets/belts/` are from
[Wikimedia Commons](https://commons.wikimedia.org/wiki/Category:SVG_Judo_belts) and
licensed [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/):
white by Buddy23Lee and Spoxjox; yellow, orange, green, blue and brown by Spoxjox;
black by Grook Da Oger; all vector-adapted by Jdcollins13.
