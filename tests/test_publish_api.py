"""
Tests for POST /api/projects/{id}/publish — network-free (GitHub HTTP + DB mocked).
"""
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app
from auth import crypto
from auth.dependencies import get_current_user

client = TestClient(app)

_SANDPACK_FILES = {
    "/App.js": 'import "./styles.css";\nexport default function App(){return <h1>Hi</h1>;}\n',
    "/styles.css": "body{margin:0}\n",
    "/package.json": '{"name":"x","dependencies":{"react":"^18.2.0","react-dom":"^18.2.0"}}',
}


def _mock_session_with_project(row):
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.get = MagicMock(return_value=row)
    return session


def _project_row(user_id, title="My Dashboard", framework="react", files=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        title=title,
        framework=framework,
        files=files if files is not None else _SANDPACK_FILES,
    )


def _override_user(github_connected: bool):
    uid = uuid.uuid4()
    enc = crypto.encrypt("ghp_storedtoken") if github_connected else None
    user = SimpleNamespace(id=uid, email="u@x.com", name="U", role="user",
                           github_token_enc=enc, github_login="octocat" if github_connected else None)
    app.dependency_overrides[get_current_user] = lambda: user
    return user


def test_publish_returns_repo_and_vercel_urls():
    user = _override_user(github_connected=True)
    row = _project_row(user.id)
    pid = str(row.id)
    repo_url = "https://github.com/octocat/appsmith-my-dashboard"
    with (
        patch("api.projects.SessionLocal", return_value=_mock_session_with_project(row)),
        patch("api.projects.publish_files", return_value=repo_url) as pub,
    ):
        r = client.post(f"/api/projects/{pid}/publish")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["repo_url"] == repo_url
    assert body["vercel_import_url"] == f"https://vercel.com/new/clone?repository-url={repo_url}"
    # repo name slugified from the title
    assert pub.call_args.args[1] == "appsmith-my-dashboard"
    # the stored token is decrypted and passed to GitHub, never the ciphertext
    assert pub.call_args.args[0] == "ghp_storedtoken"


def test_publish_without_token_returns_400():
    user = _override_user(github_connected=False)
    row = _project_row(user.id)
    with patch("api.projects.SessionLocal", return_value=_mock_session_with_project(row)):
        r = client.post(f"/api/projects/{row.id}/publish")
    assert r.status_code == 400
    assert "Connect GitHub" in r.json()["detail"]


def test_publish_foreign_project_returns_404():
    _override_user(github_connected=True)
    row = _project_row(uuid.uuid4())  # owned by a different user
    with patch("api.projects.SessionLocal", return_value=_mock_session_with_project(row)):
        r = client.post(f"/api/projects/{row.id}/publish")
    assert r.status_code == 404


def test_publish_uses_vite_transform_for_react_framework():
    """react project → publish_files receives a Vite-shaped repo (index.html + vite.config.js)."""
    import json as _json
    user = _override_user(github_connected=True)
    row = _project_row(user.id, framework="react")
    repo_url = "https://github.com/octocat/appsmith-my-dashboard"
    with (
        patch("api.projects.SessionLocal", return_value=_mock_session_with_project(row)),
        patch("api.projects.publish_files", return_value=repo_url) as pub,
    ):
        r = client.post(f"/api/projects/{row.id}/publish")
    assert r.status_code == 200
    pushed_files: dict = pub.call_args.args[2]
    assert "index.html" in pushed_files
    assert "vite.config.js" in pushed_files
    assert "src/main.jsx" in pushed_files


def test_publish_static_sends_raw_files_at_root():
    """static project → publish_files receives index.html at root, no Vite toolchain."""
    user = _override_user(github_connected=True)
    static_files = {
        "/index.html": "<!doctype html><html><body><h1>hi</h1></body></html>",
        "/styles.css": "body{margin:0}",
    }
    row = _project_row(user.id, framework="static", files=static_files)
    repo_url = "https://github.com/octocat/appsmith-my-dashboard"
    with (
        patch("api.projects.SessionLocal", return_value=_mock_session_with_project(row)),
        patch("api.projects.publish_files", return_value=repo_url) as pub,
    ):
        r = client.post(f"/api/projects/{row.id}/publish")
    assert r.status_code == 200
    pushed_files: dict = pub.call_args.args[2]
    assert "index.html" in pushed_files        # root-level (no leading slash)
    assert "/index.html" not in pushed_files   # never with leading slash
    assert "vite.config.js" not in pushed_files
    assert "package.json" not in pushed_files
    assert ".gitignore" in pushed_files
    assert "README.md" in pushed_files


def test_publish_nextjs_sends_next_files_with_correct_scripts():
    """nextjs project → package.json has next dev/build/start scripts, app/ preserved."""
    import json as _json
    user = _override_user(github_connected=True)
    next_files = {
        "/app/page.tsx": "export default function Page(){ return <h1>Hi</h1>; }",
        "/app/layout.tsx": "export default function Root({children}){ return <html><body>{children}</body></html>; }",
        "/package.json": _json.dumps({"name": "x", "dependencies": {"next": "^14.2.0", "react": "^18.2.0", "react-dom": "^18.2.0"}}),
    }
    row = _project_row(user.id, framework="nextjs", files=next_files)
    repo_url = "https://github.com/octocat/appsmith-my-dashboard"
    with (
        patch("api.projects.SessionLocal", return_value=_mock_session_with_project(row)),
        patch("api.projects.publish_files", return_value=repo_url) as pub,
    ):
        r = client.post(f"/api/projects/{row.id}/publish")
    assert r.status_code == 200
    pushed_files: dict = pub.call_args.args[2]
    pkg = _json.loads(pushed_files["package.json"])
    assert pkg["scripts"]["dev"] == "next dev"
    assert pkg["scripts"]["build"] == "next build"
    assert pkg["scripts"]["start"] == "next start"
    assert "next" in pkg["dependencies"]
    assert "app/page.tsx" in pushed_files      # app/ files preserved
    assert "vite.config.js" not in pushed_files
    assert ".gitignore" in pushed_files
    assert ".next" in pushed_files[".gitignore"]


def test_publish_old_row_without_framework_attr_defaults_react():
    """Rows that predate the framework column (no attr) fall back to react/Vite."""
    user = _override_user(github_connected=True)
    # SimpleNamespace row without framework attribute at all
    row = SimpleNamespace(
        id=uuid.uuid4(), user_id=user.id, title="Old Project", files=_SANDPACK_FILES
    )
    repo_url = "https://github.com/octocat/appsmith-old-project"
    with (
        patch("api.projects.SessionLocal", return_value=_mock_session_with_project(row)),
        patch("api.projects.publish_files", return_value=repo_url) as pub,
    ):
        r = client.post(f"/api/projects/{row.id}/publish")
    assert r.status_code == 200
    pushed_files: dict = pub.call_args.args[2]
    assert "vite.config.js" in pushed_files   # defaulted to react/Vite


def test_publish_github_error_returns_502():
    from integrations.github_client import GitHubError
    user = _override_user(github_connected=True)
    row = _project_row(user.id)
    with (
        patch("api.projects.SessionLocal", return_value=_mock_session_with_project(row)),
        patch("api.projects.publish_files", side_effect=GitHubError("GitHub could not create the repository (status 403)")),
    ):
        r = client.post(f"/api/projects/{row.id}/publish")
    assert r.status_code == 502
    assert "ghp_storedtoken" not in r.text  # token never leaks
