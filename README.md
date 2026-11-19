# Hajime

A small desktop productivity app built with Python and Tkinter. Track tasks,
build Judo belt progress, and focus with a 25/5 Pomodoro timer.

## Run

Requires Python 3.10 or newer with Tkinter available.

- Windows: double-click `start.bat`.
- Any platform: run `python -m hajime` from the project directory.
- Compatibility entry point: `python main.py`.

The app has no required third-party runtime dependencies. It renders the
included Wikimedia SVG artwork directly with Tkinter. For smoother raster
rendering, install the optional CairoSVG extra:

```sh
python -m pip install -e ".[svg]"
```

## Features

- Add, complete, edit, drag to reorder, and remove tasks.
- Progress through seven belt colors as tasks are completed.
- Run independent 25-minute work and 5-minute break sessions.
- Save the current task list and today's accumulated work time in
  `hajime_tasks.json`.

## Project layout

```text
hajime/
  app.py                 Tkinter interface and interaction logic
  belt_art.py            SVG loading and native Tk fallback
  config.py              Paths, belt ranks, timer settings, and theme
  storage.py             JSON persistence and legacy data loading
  assets/belts/          Wikimedia Commons belt illustrations
  __main__.py            Module entry point
main.py                  Compatibility entry point
start.bat                Windows launcher
hajime_tasks.json        Local user data (created/updated at runtime)
```

## Licensing

Application code is MIT licensed; Wikimedia belt artwork retains its own
CC BY-SA 3.0 license. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for
asset credits and [LICENSE](LICENSE) for the code license.
