"""Cloud tests against a tiny in-process fake of the Supabase HTTP API."""

import json
import queue
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from hajime import cloud, storage


class FakeSupabase(BaseHTTPRequestHandler):
    rows: dict = {}
    token_calls: list = []

    def _send(self, body, status=200):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")

    def do_POST(self):
        url = urlparse(self.path)
        body = self._body()
        if url.path == "/auth/v1/token":
            grant = parse_qs(url.query)["grant_type"][0]
            self.token_calls.append((grant, body))
            if grant == "refresh_token" and body["refresh_token"] == "revoked":
                return self._send({"error_description": "Invalid Refresh Token"}, 400)
            self._send({"access_token": "jwt", "refresh_token": "r2", "expires_in": 3600,
                        "user": {"id": "11111111-2222-3333-4444-555555555555",
                                 "email": "a@b.c"}})
        elif url.path == "/rest/v1/user_data":
            self.rows[body["user_id"]] = {"data": body["data"], "updated_by": body["updated_by"]}
            self._send(None, 201)
        else:
            self._send({}, 404)

    def do_GET(self):
        uid = parse_qs(urlparse(self.path).query)["user_id"][0].removeprefix("eq.")
        row = self.rows.get(uid)
        self._send([{"data": row["data"]}] if row else [])

    def log_message(self, *_args):
        pass


@pytest.fixture
def server(monkeypatch, tmp_path):
    FakeSupabase.rows, FakeSupabase.token_calls = {}, []
    httpd = HTTPServer(("127.0.0.1", 0), FakeSupabase)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setattr(cloud, "PUSH_DEBOUNCE", 0.0)
    yield cloud.SupabaseConfig(f"http://127.0.0.1:{httpd.server_port}", "anon")
    httpd.shutdown()


def make_auth(config, tmp_path):
    return cloud.SupabaseAuth(config, tmp_path / "session.json")


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("HAJIME_SUPABASE_URL", "https://x.supabase.co/")
    monkeypatch.setenv("HAJIME_SUPABASE_ANON_KEY", "key")
    config = cloud.load_config()
    assert config == cloud.SupabaseConfig("https://x.supabase.co", "key")
    assert config.realtime_url.startswith("wss://x.supabase.co/realtime/v1/websocket?apikey=key")


def test_google_sign_in_uses_pkce_and_persists_session(server, tmp_path):
    auth = make_auth(server, tmp_path)
    seen = {}

    def fake_browser(url):
        query = parse_qs(urlparse(url).query)
        seen.update(query)

        def callback():
            urllib.request.urlopen(f"{cloud.REDIRECT_URI}?code=abc", timeout=5).read()

        threading.Thread(target=callback, daemon=True).start()

    session = auth.sign_in_with_google(threading.Event(), timeout=10, open_browser=fake_browser)
    assert seen["provider"] == ["google"]
    assert seen["code_challenge_method"] == ["s256"]
    grant, body = FakeSupabase.token_calls[0]
    assert grant == "pkce" and body["auth_code"] == "abc"
    assert len(body["code_verifier"]) >= 43
    assert (session.user_id, session.email) == (
        "11111111-2222-3333-4444-555555555555", "a@b.c")
    assert make_auth(server, tmp_path).load_saved().refresh_token == "r2"


def test_sign_in_can_be_cancelled(server, tmp_path):
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(cloud.CloudError, match="cancelled"):
        make_auth(server, tmp_path).sign_in_with_google(cancel, open_browser=lambda _u: None)


def test_revoked_refresh_token_clears_session(server, tmp_path):
    auth = make_auth(server, tmp_path)
    auth.session = cloud.Session("old", "revoked", 0, "user-1", "a@b.c")
    auth._persist()
    with pytest.raises(cloud.CloudError):
        auth.access_token()
    assert auth.session is None and not (tmp_path / "session.json").exists()


def wait_for(events, name, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            event, payload = events.get(timeout=0.1)
        except queue.Empty:
            continue
        if event == name:
            return payload
    raise AssertionError(f"no {name!r} event")


def signed_in(server, tmp_path):
    auth = make_auth(server, tmp_path)
    auth.session = cloud.Session("jwt", "r", time.time() + 3600, "user-1", "a@b.c")
    return auth


def test_first_sync_uploads_local_data_then_other_device_pulls_it(server, tmp_path, monkeypatch):
    monkeypatch.setattr(cloud._Realtime, "run", lambda self: None)  # no websocket here
    local = storage.to_payload(storage.AppData())
    local["boards"][0]["tasks"] = [{"title": "uchi komi", "done": True}]

    events = queue.Queue()
    first = cloud.CloudSync(signed_in(server, tmp_path), "dev-a", lambda e, p: events.put((e, p)))
    first.start(local)
    wait_for(events, "synced")
    deadline = time.monotonic() + 5
    while "user-1" not in FakeSupabase.rows and time.monotonic() < deadline:
        time.sleep(0.05)
    assert FakeSupabase.rows["user-1"]["updated_by"] == "dev-a"
    first.stop()

    events = queue.Queue()
    second = cloud.CloudSync(signed_in(server, tmp_path), "dev-b", lambda e, p: events.put((e, p)))
    second.start(storage.to_payload(storage.AppData()))
    remote = wait_for(events, "remote")
    assert storage.from_payload(remote).boards[0].tasks[0].title == "uchi komi"
    second.stop()


def test_realtime_ignores_own_echo_and_forwards_other_devices():
    emitted = []
    sync = cloud.CloudSync(None, "me", lambda e, p: emitted.append((e, p)))
    realtime = cloud._Realtime(sync)

    def change(author):
        return {"event": "postgres_changes", "payload": {"data": {
            "type": "UPDATE", "record": {"data": {"boards": []}, "updated_by": author}}}}

    realtime._handle(change("me"))
    realtime._handle(change("other"))
    assert emitted == [("remote", {"boards": []})]


def test_config_url_keeps_only_the_host(monkeypatch):
    monkeypatch.setenv("HAJIME_SUPABASE_URL", "https://x.supabase.co/rest/v1/")
    monkeypatch.setenv("HAJIME_SUPABASE_ANON_KEY", "key")
    assert cloud.load_config().url == "https://x.supabase.co"


def test_empty_remote_copy_does_not_wipe_local_tasks(server, tmp_path, monkeypatch):
    monkeypatch.setattr(cloud._Realtime, "run", lambda self: None)
    FakeSupabase.rows["user-1"] = {"data": storage.to_payload(storage.AppData()),
                                   "updated_by": "x"}
    local = storage.to_payload(storage.AppData())
    local["boards"][0]["tasks"] = [{"title": "keep me", "done": False}]
    events = queue.Queue()
    sync = cloud.CloudSync(signed_in(server, tmp_path), "dev", lambda e, p: events.put((e, p)))
    sync.start(local)
    wait_for(events, "synced")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        tasks = storage.from_payload(FakeSupabase.rows["user-1"]["data"]).board.tasks
        if tasks:
            break
        time.sleep(0.05)
    assert [t.title for t in tasks] == ["keep me"]
    sync.stop()


def test_insecure_or_malformed_urls_are_rejected(monkeypatch):
    monkeypatch.setenv("HAJIME_SUPABASE_ANON_KEY", "key")
    for url in ("http://x.supabase.co", "ftp://x.co", "x.supabase.co", ""):
        monkeypatch.setenv("HAJIME_SUPABASE_URL", url)
        monkeypatch.setattr(cloud, "config_path", lambda: Path("nope.json"))
        assert cloud.load_config() is None, url
    monkeypatch.setenv("HAJIME_SUPABASE_URL", "http://127.0.0.1:54321")
    assert cloud.load_config() is not None  # local development stack


def test_account_id_must_be_a_uuid(server, tmp_path):
    auth = make_auth(server, tmp_path)
    bad = {"access_token": "a", "refresh_token": "b", "expires_in": 60,
           "user": {"id": "../../evil", "email": "x"}}
    with pytest.raises(cloud.CloudError):
        auth._adopt(bad)
    assert auth.session is None


def test_session_file_is_encrypted_on_windows_and_upgrades_old_files(server, tmp_path):
    import sys

    auth = make_auth(server, tmp_path)
    uid = "274154f0-2f11-46ea-93c5-c93abfc5a33f"
    legacy = {"access_token": "SECRET-TOKEN", "refresh_token": "r", "expires_at": 9e12,
              "user_id": uid, "email": "a@b.c"}
    (tmp_path / "session.json").write_text(json.dumps(legacy))  # an older plain-text file
    assert auth.load_saved().access_token == "SECRET-TOKEN"
    stored = (tmp_path / "session.json").read_bytes()
    assert (b"SECRET-TOKEN" not in stored) == (sys.platform == "win32")
    assert make_auth(server, tmp_path).load_saved().access_token == "SECRET-TOKEN"


def test_callback_port_cannot_be_shared():
    import socket

    first = cloud._LoopbackServer(("127.0.0.1", 0), cloud._CallbackHandler)
    try:
        port = first.server_port
        with pytest.raises(OSError):
            cloud._LoopbackServer(("127.0.0.1", port), cloud._CallbackHandler)
        probe = socket.socket()
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            with pytest.raises(OSError):
                probe.bind(("127.0.0.1", port))
        finally:
            probe.close()
    finally:
        first.server_close()


def wait_until(condition, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return False


def test_changes_made_offline_are_retried_until_they_arrive(server, tmp_path, monkeypatch):
    monkeypatch.setattr(cloud._Realtime, "run", lambda self: None)
    monkeypatch.setattr(cloud, "RETRY_SECONDS", 0.05)
    events = queue.Queue()
    sync = cloud.CloudSync(signed_in(server, tmp_path), "dev", lambda e, p: events.put((e, p)))
    sync.start(storage.to_payload(storage.AppData()))
    wait_for(events, "synced")

    real_upsert, attempts = sync._upsert, []

    def flaky(payload, timeout=15):
        attempts.append(1)
        if len(attempts) <= 2:
            raise cloud.NetworkError("offline")
        real_upsert(payload, timeout)

    monkeypatch.setattr(sync, "_upsert", flaky)
    edited = storage.to_payload(storage.AppData())
    edited["boards"][0]["tasks"] = [{"title": "written offline", "done": False}]
    seq = sync.push(edited)
    assert wait_for(events, "pushed") == seq
    assert len(attempts) == 3
    saved = storage.from_payload(FakeSupabase.rows["user-1"]["data"])
    assert saved.board.tasks[0].title == "written offline"
    sync.stop()


def test_unsynced_edits_are_merged_not_overwritten_after_restart(server, tmp_path, monkeypatch):
    monkeypatch.setattr(cloud._Realtime, "run", lambda self: None)
    phone = storage.AppData(boards=[storage.Board("Phone", [storage.Task("from phone")])],
                            history={"2026-01-01": 100})
    FakeSupabase.rows["user-1"] = {"data": storage.to_payload(phone), "updated_by": "x"}
    laptop = storage.AppData(boards=[storage.Board("Tasks", [storage.Task("offline edit")])],
                             history={"2026-01-01": 900})
    events = queue.Queue()
    sync = cloud.CloudSync(signed_in(server, tmp_path), "laptop", lambda e, p: events.put((e, p)))
    sync.start(storage.to_payload(laptop), unsynced=True)
    shown = storage.from_payload(wait_for(events, "remote"))
    assert [b.name for b in shown.boards] == ["Tasks", "Phone"]
    assert wait_until(lambda: FakeSupabase.rows["user-1"]["updated_by"] == "laptop")
    stored = storage.from_payload(FakeSupabase.rows["user-1"]["data"])
    assert [b.name for b in stored.boards] == ["Tasks", "Phone"]
    assert stored.boards[0].tasks[0].title == "offline edit"
    assert stored.history == {"2026-01-01": 900}
    sync.stop()


def test_without_unsynced_edits_the_cloud_copy_wins(server, tmp_path, monkeypatch):
    monkeypatch.setattr(cloud._Realtime, "run", lambda self: None)
    phone = storage.AppData(boards=[storage.Board("Phone", [storage.Task("from phone")])])
    FakeSupabase.rows["user-1"] = {"data": storage.to_payload(phone), "updated_by": "x"}
    events = queue.Queue()
    sync = cloud.CloudSync(signed_in(server, tmp_path), "laptop", lambda e, p: events.put((e, p)))
    sync.start(storage.to_payload(storage.AppData(boards=[storage.Board("Old", [])])))
    shown = storage.from_payload(wait_for(events, "remote"))
    assert [b.name for b in shown.boards] == ["Phone"]
    sync.stop()
