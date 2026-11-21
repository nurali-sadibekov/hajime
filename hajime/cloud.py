"""Supabase integration: Google sign-in (OAuth + PKCE), remote storage and realtime sync.

Only the standard library plus ``websocket-client`` is used. Nothing here touches Tk;
background threads report back through the ``emit(event, payload)`` callback.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import secrets
import socket
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from . import secure_store, storage

LOG = logging.getLogger("hajime")

CALLBACK_PORT = 53682
REDIRECT_URI = f"http://127.0.0.1:{CALLBACK_PORT}/callback"
TABLE = "user_data"
REFRESH_MARGIN = 60  # seconds before expiry at which the token is renewed
PUSH_DEBOUNCE = 0.6
HEARTBEAT_SECONDS = 25
UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
MAX_RESPONSE_BYTES = 8_000_000  # far above the largest legitimate data row


class CloudError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class NetworkError(CloudError):
    """The server could not be reached."""


# ----- configuration --------------------------------------------------------
@dataclass(frozen=True)
class SupabaseConfig:
    url: str
    anon_key: str

    @property
    def realtime_url(self) -> str:
        host = self.url.split("://", 1)[-1]
        scheme = "ws" if self.url.startswith("http://") else "wss"
        return f"{scheme}://{host}/realtime/v1/websocket?" + urlencode(
            {"apikey": self.anon_key, "vsn": "1.0.0"})


def config_path() -> Path:
    return storage.default_data_path().with_name("supabase.json")


def load_config() -> SupabaseConfig | None:
    """Read the project URL and anon key from the environment or ``supabase.json``."""
    url = os.environ.get("HAJIME_SUPABASE_URL", "")
    key = os.environ.get("HAJIME_SUPABASE_ANON_KEY", "")
    if not (url and key):
        try:
            raw = json.loads(config_path().read_text(encoding="utf-8"))
            url, key = str(raw.get("url", "")), str(raw.get("anon_key", ""))
        except (OSError, ValueError, AttributeError):
            pass
    if not (url and key):  # values baked in by build.bat
        try:
            from . import _bundled_config  # type: ignore[attr-defined]

            url, key = _bundled_config.URL, _bundled_config.ANON_KEY
        except (ImportError, AttributeError):
            pass
    parsed = urlparse(url.strip())
    key = key.strip()
    loopback = parsed.hostname in ("localhost", "127.0.0.1", "::1")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
        return None  # tokens must never travel over plain http
    if not parsed.netloc or not key:
        return None
    # Keep only scheme://host: a pasted ".../rest/v1" or trailing slash must not leak in.
    return SupabaseConfig(f"{parsed.scheme}://{parsed.netloc}", key)


# ----- HTTP -----------------------------------------------------------------
def _error_text(body: bytes) -> str:
    try:
        raw = json.loads(body)
        return str(raw.get("error_description") or raw.get("msg") or raw.get("message")
                   or raw.get("error") or body[:200])
    except (ValueError, AttributeError):
        return body[:200].decode("utf-8", "replace")


def _request(method: str, url: str, headers: dict[str, str], body: object = None,
             timeout: float = 15) -> object:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        url, data=data, method=method, headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        raise CloudError(_error_text(error.read(2000)), error.code) from None
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise NetworkError(str(getattr(error, "reason", error))) from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise CloudError("The server sent an unexpectedly large response.")
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        raise CloudError("The server sent an unreadable response.") from None


# ----- auth -----------------------------------------------------------------
@dataclass
class Session:
    access_token: str
    refresh_token: str
    expires_at: float
    user_id: str
    email: str


def session_path() -> Path:
    return storage.default_data_path().with_name("session.json")


class _CallbackHandler(BaseHTTPRequestHandler):
    STYLE = (b"<!doctype html><meta charset=utf-8><title>Hajime</title>"
             b"<body style='font:16px system-ui;text-align:center;margin-top:20vh;color:#242522'>")
    OK = STYLE + b"<h2>You're signed in.</h2><p>You can close this tab and return to Hajime.</p>"
    FAILED = STYLE + b"<h2>Sign-in did not complete.</h2><p>Return to Hajime and try again.</p>"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_error(404)
            return
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        if self.server.result is None and ("code" in query or "error" in query):  # type: ignore[attr-defined]
            self.server.result = query  # type: ignore[attr-defined]
        page = self.OK if "code" in query else self.FAILED
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(page)

    def log_message(self, *_args) -> None:
        pass


class _LoopbackServer(HTTPServer):
    # Windows lets a second process share a port when SO_REUSEADDR is set, which would let
    # another program sit on the callback port and read the sign-in code. Refuse sharing.
    allow_reuse_address = False

    def server_bind(self) -> None:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class SupabaseAuth:
    def __init__(self, config: SupabaseConfig, path: Path | None = None) -> None:
        self.config = config
        self.path = path or session_path()
        self.session: Session | None = None
        self._lock = threading.RLock()

    @property
    def _headers(self) -> dict[str, str]:
        return {"apikey": self.config.anon_key}

    # persistence
    def load_saved(self) -> Session | None:
        try:
            raw = json.loads(secure_store.read(self.path))
            session = Session(
                str(raw["access_token"]), str(raw["refresh_token"]),
                float(raw["expires_at"]), str(raw["user_id"]), str(raw.get("email", "")))
            if not UUID_RE.fullmatch(session.user_id):
                raise ValueError("bad user id")
            self.session = session
            if not self.path.read_bytes().startswith(secure_store.MARKER):
                self._persist()  # upgrade a plain-text file written by an older version
        except (OSError, ValueError, KeyError, TypeError):
            self.session = None
        return self.session

    def _persist(self) -> None:
        try:
            secure_store.write(self.path, json.dumps(asdict(self.session)))
        except OSError:
            LOG.warning("could not store the session")

    def _clear(self) -> None:
        self.session = None
        try:
            self.path.unlink()
        except OSError:
            pass

    def _adopt(self, response: dict) -> Session:
        try:
            user = response.get("user") or {}
            previous = self.session
            session = Session(
                access_token=str(response["access_token"]),
                refresh_token=str(response["refresh_token"]),
                expires_at=float(
                    response.get("expires_at") or time.time() + float(response["expires_in"])),
                user_id=str(user.get("id") or (previous.user_id if previous else "")),
                email=str(user.get("email") or (previous.email if previous else "")),
            )
        except (AttributeError, KeyError, TypeError, ValueError):
            raise CloudError("The server sent an unexpected sign-in response.") from None
        if not UUID_RE.fullmatch(session.user_id):  # it ends up in URLs and file names
            raise CloudError("The server sent an invalid account id.")
        self.session = session
        self._persist()
        return session

    # token lifecycle
    def refresh(self) -> Session:
        with self._lock:
            if self.session is None:
                raise CloudError("not signed in", 401)
            try:
                response = _request(
                    "POST", f"{self.config.url}/auth/v1/token?grant_type=refresh_token",
                    self._headers, {"refresh_token": self.session.refresh_token})
            except NetworkError:
                raise
            except CloudError:
                self._clear()  # the refresh token was revoked or is invalid
                raise
            return self._adopt(response)  # type: ignore[arg-type]

    def access_token(self) -> str:
        with self._lock:
            if self.session is None:
                raise CloudError("not signed in", 401)
            if self.session.expires_at - time.time() < REFRESH_MARGIN:
                self.refresh()
            return self.session.access_token

    def sign_out(self) -> None:
        """Forget the session now; revoke it on the server in the background."""
        with self._lock:
            session = self.session
            self._clear()
        if session is not None:
            def revoke() -> None:
                try:
                    _request("POST", f"{self.config.url}/auth/v1/logout",
                             {**self._headers, "Authorization": f"Bearer {session.access_token}"},
                             timeout=5)
                except CloudError:
                    pass
            threading.Thread(target=revoke, daemon=True).start()

    def sign_in_with_google(self, cancel: threading.Event, timeout: float = 180,
                            open_browser=webbrowser.open) -> Session:
        """Run the browser OAuth flow (PKCE) and block until it completes."""
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        try:
            server = _LoopbackServer(("127.0.0.1", CALLBACK_PORT), _CallbackHandler)
        except OSError as error:
            raise CloudError(f"Port {CALLBACK_PORT} is busy; close the other Hajime window "
                             f"and try again ({error.strerror}).") from None
        server.result = None  # type: ignore[attr-defined]
        server.timeout = 0.4
        url = f"{self.config.url}/auth/v1/authorize?" + urlencode({
            "provider": "google", "redirect_to": REDIRECT_URI, "apikey": self.config.anon_key,
            "code_challenge": challenge, "code_challenge_method": "s256"})
        try:
            open_browser(url)
            deadline = time.monotonic() + timeout
            while (server.result is None and not cancel.is_set()
                   and time.monotonic() < deadline):
                server.handle_request()
            result = server.result  # type: ignore[attr-defined]
        finally:
            server.server_close()
        if cancel.is_set():
            raise CloudError("cancelled")
        if result is None:
            raise CloudError("Sign-in timed out.")
        if "code" not in result:
            raise CloudError(result.get("error_description") or result.get("error", "failed"))
        response = _request(
            "POST", f"{self.config.url}/auth/v1/token?grant_type=pkce", self._headers,
            {"auth_code": result["code"], "code_verifier": verifier})
        with self._lock:
            return self._adopt(response)  # type: ignore[arg-type]


# ----- sync -----------------------------------------------------------------
class CloudSync:
    """Mirrors the user's data in one Supabase row and listens for remote changes.

    Events passed to ``emit``: ``("remote", payload)`` a newer copy from another device,
    ``("synced", None)`` the first pull finished, ``("status", "online"|"offline")`` and
    ``("auth_lost", None)`` when the session can no longer be renewed.
    """

    def __init__(self, auth: SupabaseAuth, client_id: str, emit) -> None:
        self.auth = auth
        self.client_id = client_id
        self._emit = emit
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._lock = threading.Lock()
        self._pending: dict | None = None
        self._need_pull = False
        self._online: bool | None = None

    def start(self, local_payload: dict) -> None:
        self._pending = None
        threading.Thread(target=self._run, args=(local_payload,), daemon=True).start()
        _Realtime(self).start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def push(self, payload: dict) -> None:
        with self._lock:
            self._pending = payload
        self._wake.set()

    def request_pull(self) -> None:
        self._need_pull = True
        self._wake.set()

    # REST helpers
    def _rest(self, method: str, query: str = "", body: object = None,
              extra: dict[str, str] | None = None, timeout: float = 15):
        url = f"{self.auth.config.url}/rest/v1/{TABLE}{query}"
        for attempt in (0, 1):
            headers = {"apikey": self.auth.config.anon_key,
                       "Authorization": f"Bearer {self.auth.access_token()}", **(extra or {})}
            try:
                return _request(method, url, headers, body, timeout)
            except CloudError as error:
                if error.status == 401 and attempt == 0:
                    self.auth.refresh()
                    continue
                raise

    def _pull(self) -> dict | None:
        uid = self.auth.session.user_id  # type: ignore[union-attr]
        rows = self._rest("GET", f"?select=data&user_id=eq.{uid}")
        return rows[0]["data"] if rows else None  # type: ignore[index]

    def flush(self) -> None:
        """Stop syncing and send any unsent change right now (used when quitting)."""
        self._stop.set()
        self._wake.set()
        with self._lock:
            payload = self._pending
        if payload is not None and self._online is not False:
            try:
                self._upsert(payload, timeout=4)
            except CloudError:
                pass

    def _upsert(self, payload: dict, timeout: float = 15) -> None:
        self._rest(
            "POST", "?on_conflict=user_id",
            {"user_id": self.auth.session.user_id,  # type: ignore[union-attr]
             "data": payload, "updated_by": self.client_id},
            {"Prefer": "resolution=merge-duplicates,return=minimal"}, timeout)

    def _set_online(self, online: bool) -> None:
        if online != self._online:
            self._online = online
            self._emit("status", "online" if online else "offline")

    def _guard(self, action):
        """Run ``action``; returns ``(ok, result)`` and reports connectivity."""
        try:
            result = action()
        except NetworkError:
            self._set_online(False)
            return False, None
        except CloudError as error:
            if error.status in (400, 401, 403) and self.auth.session is None:
                self._emit("auth_lost", None)
                self._stop.set()
            else:
                LOG.warning("sync request failed: %s", error)
                self._set_online(False)
            return False, None
        self._set_online(True)
        return True, result

    def _run(self, local_payload: dict) -> None:
        delay = 2.0
        while not self._stop.is_set():
            ok, remote = self._guard(self._pull)
            if ok:
                break
            if self._stop.wait(delay):
                return
            delay = min(delay * 2, 30)
        else:
            return
        local, theirs = storage.from_payload(local_payload), storage.from_payload(remote)
        if theirs is not None and (theirs.has_content or not (local and local.has_content)):
            self._emit("remote", remote)
        else:  # nothing stored yet (or only an empty copy): upload what this device has
            self.push(local_payload)
        self._emit("synced", None)

        while not self._stop.is_set():
            self._wake.wait()
            if self._stop.is_set():
                return
            self._wake.clear()
            if self._stop.wait(PUSH_DEBOUNCE):
                return
            with self._lock:
                payload = self._pending
            if payload is not None:
                ok, _ = self._guard(lambda p=payload: self._upsert(p))
                if ok:
                    with self._lock:
                        if self._pending is payload:
                            self._pending = None
                else:
                    self._retry_later()
                    continue
            if self._need_pull:
                self._need_pull = False
                with self._lock:
                    unsent = self._pending is not None
                if not unsent:
                    ok, remote = self._guard(self._pull)
                    if ok and remote is not None:
                        self._emit("remote", remote)
                    elif not ok:
                        self._need_pull = True
                        self._retry_later()

    def _retry_later(self) -> None:
        def wake() -> None:
            if not self._stop.wait(5):
                self._wake.set()
        threading.Thread(target=wake, daemon=True).start()


class _Realtime(threading.Thread):
    """Phoenix-channel client for Supabase Realtime ``postgres_changes``."""

    def __init__(self, sync: CloudSync) -> None:
        super().__init__(daemon=True)
        self.sync = sync
        self._connected_once = False

    def run(self) -> None:
        backoff = 1.0
        while not self.sync._stop.is_set():
            try:
                self._session()
                backoff = 1.0
            except Exception as error:  # network drops, protocol errors: just reconnect
                LOG.info("realtime disconnected: %s", error)
            if self.sync._stop.wait(backoff):
                return
            backoff = min(backoff * 2, 30.0)

    def _session(self) -> None:
        import websocket  # websocket-client

        auth = self.sync.auth
        topic = "realtime:hajime-sync"
        ws = websocket.create_connection(auth.config.realtime_url, timeout=10)
        ws.settimeout(1.0)

        def send(event: str, payload: dict, to: str = topic, ref: str = "1") -> None:
            ws.send(json.dumps({"topic": to, "event": event, "payload": payload,
                                "ref": ref, "join_ref": "1"}))

        try:
            token = auth.access_token()
            send("phx_join", {
                "config": {"postgres_changes": [{
                    "event": "*", "schema": "public", "table": TABLE,
                    "filter": f"user_id=eq.{auth.session.user_id}"}]},  # type: ignore[union-attr]
                "access_token": token})
            beat, last_beat = 1, time.monotonic()
            while not self.sync._stop.is_set():
                try:
                    message = ws.recv()
                except websocket.WebSocketTimeoutException:
                    message = None
                if message == "":
                    raise ConnectionError("closed by server")
                if message:
                    self._handle(json.loads(message))
                if time.monotonic() - last_beat >= HEARTBEAT_SECONDS:
                    beat += 1
                    last_beat = time.monotonic()
                    send("heartbeat", {}, "phoenix", str(beat))
                    fresh = auth.access_token()
                    if fresh != token:
                        token = fresh
                        send("access_token", {"access_token": token}, ref=str(beat + 1000))
        finally:
            try:
                ws.close()
            except Exception:
                pass

    def _handle(self, message: dict) -> None:
        event = message.get("event")
        payload = message.get("payload") or {}
        if event == "phx_reply" and message.get("topic", "").startswith("realtime:"):
            if payload.get("status") == "ok" and message.get("ref") == "1":
                if self._connected_once:  # something may have changed while we were away
                    self.sync.request_pull()
                self._connected_once = True
        elif event in ("phx_error", "phx_close"):
            raise ConnectionError(event)
        elif event == "postgres_changes":
            data = payload.get("data") or {}
            record = data.get("record") or {}
            if (data.get("type") in ("INSERT", "UPDATE") and isinstance(record.get("data"), dict)
                    and record.get("updated_by") != self.sync.client_id):
                self.sync._emit("remote", record["data"])
