# ABOUTME: Tests that serve.py exposes the built page and items.json, and nothing else.
# ABOUTME: Starts a real server on an ephemeral localhost port.
import threading
import urllib.error
import urllib.request

import pytest

from serve import make_server


@pytest.fixture
def base_url(tmp_path):
    dist, data = tmp_path / "dist", tmp_path / "data"
    dist.mkdir()
    data.mkdir()
    (dist / "index.html").write_text("<html>dashboard</html>")
    (data / "items.json").write_text('{"items": []}')
    (data / "state.json").write_text('{"tombstones": {}}')
    (data / "attempts.json").write_text('{"attempts": {}}')
    (data / ".writer.lock").write_text("")
    server = make_server(dist, data, "127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def get(url):
    with urllib.request.urlopen(url) as response:
        return response.status, response.headers, response.read().decode()


def test_serves_the_built_page(base_url):
    status, _, body = get(base_url + "/")
    assert status == 200 and "dashboard" in body


def test_serves_items_json_from_the_data_directory_without_caching(base_url):
    status, headers, body = get(base_url + "/items.json")
    assert status == 200 and body == '{"items": []}'
    assert headers["Cache-Control"] == "no-cache"


def test_does_not_expose_private_files_or_traversal(base_url):
    for path in ("/state.json", "/../data/state.json", "/data/state.json",
                 "/attempts.json", "/../data/attempts.json", "/data/attempts.json",
                 "/.writer.lock", "/../data/.writer.lock", "/data/.writer.lock"):
        with pytest.raises(urllib.error.HTTPError) as caught:
            get(base_url + path)
        assert caught.value.code == 404
