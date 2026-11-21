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

## Accounts and sync (Supabase)

Hajime opens on a sign-in screen. **Continue with Google** signs in or creates the account
(there is no separate sign-up), and your boards, tasks and study history are stored in
Supabase and synced live between devices. A local copy is kept, so the app still works
offline and catches up when the connection returns.

One-time setup of your own Supabase project:

1. Run [`supabase/schema.sql`](supabase/schema.sql) in the SQL editor (creates the
   `user_data` table, row-level security and the realtime publication).
2. *Authentication → Providers → Google*: enable it with your Google OAuth client ID/secret
   (the Google client's redirect URI is `https://<project>.supabase.co/auth/v1/callback`).
3. *Authentication → URL Configuration → Redirect URLs*: add `http://127.0.0.1:53682/callback`.
4. Give the app the project URL and **anon** key (public by design; never use the
   service-role key), either as environment variables
   `HAJIME_SUPABASE_URL` / `HAJIME_SUPABASE_ANON_KEY`, or in `supabase.json` next to the data
   file: `{"url": "https://<project>.supabase.co", "anon_key": "..."}`.

Without that configuration the sign-in screen offers "Use without an account" (local file only).
Sync keeps one copy per account; the newest save wins, and daily study time is merged.

Data is stored per user (`%APPDATA%\Hajime`, `~/Library/Application Support/Hajime`
or `~/.local/share/Hajime`); set `HAJIME_DATA_FILE` to use another file.
Unexpected errors are logged to `hajime.log` in the same folder.

Prebuilt Windows, macOS and Linux apps are attached to each
[GitHub release](../../releases).

## Building the Windows installer

```bat
build.bat            :: lint + tests + app + installer   (build.bat fast skips lint and tests)
```

Produces `release\Hajime-Setup.exe`, a per-user installer (no administrator rights needed)
that installs `Hajime.exe`, a Start-menu entry and an uninstaller. Uninstalling keeps the
user's tasks and session in `%APPDATA%\Hajime`.

Create `build.env` next to `build.bat` (it is git-ignored):

```text
HAJIME_SUPABASE_URL=https://YOUR-PROJECT.supabase.co
HAJIME_SUPABASE_ANON_KEY=sb_publishable_...
SIGN_PFX=C:\certs\code-signing-certificate.pfx
SIGN_PASSWORD=...
```

The URL and publishable key are baked into the app so users need no setup. `build.bat`
refuses a secret/service-role key. Inno Setup 6 is installed with winget if missing.
Without `SIGN_PFX` the installer is unsigned and Windows SmartScreen will warn users.

## Before a public launch

- **Google OAuth:** in Google Cloud, *Audience* must be switched from "Testing" (100 test
  users) to "In production", with a homepage and privacy-policy URL on the Branding page.
  Only the basic sign-in scopes are used, so no Google verification review is needed.
- **Supabase plan:** the free plan caps realtime connections (200 at a time) and pauses idle
  projects. Choose a plan for your expected number of simultaneously open apps, and watch
  *Reports → Realtime* and *Database* after launch.
- **Code signing:** sign `Hajime-Setup.exe` (an OV/EV certificate) so SmartScreen and
  antivirus products trust it.
- **Known limit:** each account's data is one document and the newest save wins, so two
  devices edited at the same moment can overwrite each other's changes (study time is merged).

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
  cloud.py       Supabase auth (Google/PKCE), remote storage, realtime sync
  secure_store.py Encrypts the saved login session (Windows DPAPI)
  auth_screen.py Sign-in screen
  app.py         CustomTkinter UI
  belt_art.py    SVG belt rendering
  config.py      Belts, timer lengths, theme
supabase/        SQL schema for the backend
packaging/       Launcher, icon and config scripts for frozen builds
installer/       Inno Setup script (built by build.bat)
tests/           pytest suite
```

## License

Code: MIT ([LICENSE](LICENSE)).

Belt illustrations in `hajime/assets/belts/` are from
[Wikimedia Commons](https://commons.wikimedia.org/wiki/Category:SVG_Judo_belts) and
licensed [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/):
white by Buddy23Lee and Spoxjox; yellow, orange, green, blue and brown by Spoxjox;
black by Grook Da Oger; all vector-adapted by Jdcollins13.
