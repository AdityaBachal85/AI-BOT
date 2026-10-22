#!/usr/bin/env python3
"""Configure Open WebUI for the company. Safe to run as often as you like.

Each run:
  1. signs in with the admin account from .env
  2. waits until the AI models have finished downloading
  3. applies the sign-up and document-search settings
  4. syncs company-docs/ into the "Company Documents" library
     (uploads new files, re-uploads changed files, removes deleted files)
  5. creates or updates the assistants defined in assistants/*.md

Run it with:  docker compose run --rm setup
Uses only the Python standard library.
"""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

WEBUI_URL = os.environ.get("WEBUI_URL", "http://localhost:3000").rstrip("/")
PUBLIC_URL = os.environ.get("PUBLIC_URL", WEBUI_URL)
KIT_DIR = Path(os.environ.get("KIT_DIR") or Path(__file__).resolve().parent.parent)
DOCS_DIR = KIT_DIR / "company-docs"
ASSISTANTS_DIR = KIT_DIR / "assistants"

COMPANY_NAME = os.environ.get("COMPANY_NAME", "our company")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "gemma4:e4b")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "embeddinggemma")
DEFAULT_ASSISTANT = os.environ.get("DEFAULT_ASSISTANT", "company-knowledge")
MODEL_WAIT_MINUTES = int(os.environ.get("MODEL_WAIT_MINUTES", "120"))

LIBRARY_NAME = "Company Documents"
LIBRARY_DESCRIPTION = "Company documents synced from the company-docs folder by setup."
# Every signed-in, approved user can read. Only admins can change.
EVERYONE_CAN_READ = [{"principal_type": "user", "principal_id": "*", "permission": "read"}]

# Sent to the model together with the document excerpts found for a question.
# {{CONTEXT}} is replaced by the excerpts.
RAG_TEMPLATE = """Company document excerpts related to the user's message are given below.

Rules:
- Take company facts only from these excerpts. If a needed fact is not in them, say so plainly or use a placeholder like [DETAIL]. Never guess.
- When you use an excerpt, cite its number in square brackets, like [1]. Cite only excerpts that have an id attribute.
- Do not use XML tags in your reply.
- Reply in the same language as the user's message.

<context>
{{CONTEXT}}
</context>
"""

# Mostly-binary formats the server may not detect from the name alone.
CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".csv": "text/csv",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".html": "text/html",
    ".htm": "text/html",
    ".json": "application/json",
    ".rtf": "application/rtf",
    ".epub": "application/epub+zip",
}


class ApiError(Exception):
    def __init__(self, status, detail):
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


def say(msg=""):
    print(msg, flush=True)


def fail(msg):
    say(f"\nERROR: {msg}")
    sys.exit(1)


def api(method, path, body=None, token=None, data=None, content_type=None, timeout=60):
    if body is not None:
        data = json.dumps(body).encode()
        content_type = "application/json"
    req = urllib.request.Request(WEBUI_URL + path, data=data, method=method)
    if content_type:
        req.add_header("Content-Type", content_type)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        try:
            detail = json.loads(detail).get("detail", detail)
        except (ValueError, AttributeError):
            pass
        raise ApiError(e.code, detail) from None
    return json.loads(text) if text else None


# ---------------------------------------------------------------- 1. sign in


def wait_for_server():
    say(f"Connecting to Open WebUI at {WEBUI_URL} ...")
    deadline = time.time() + 600
    while time.time() < deadline:
        try:
            if api("GET", "/health", timeout=5).get("status"):
                return
        except (urllib.error.URLError, ApiError, OSError, ValueError, AttributeError):
            pass
        time.sleep(3)
    fail("Open WebUI did not start within 10 minutes. Check: docker compose logs open-webui")


def sign_in():
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        fail("ADMIN_EMAIL and ADMIN_PASSWORD must be set in .env")
    try:
        res = api("POST", "/api/v1/auths/signin", {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    except ApiError as e:
        fail(
            f"Could not sign in as {ADMIN_EMAIL} ({e.detail}).\n"
            "  If you changed the admin password in the web app, put the new one in .env as ADMIN_PASSWORD.\n"
            "  If the very first account was created by hand, use that account's email and password."
        )
    if res.get("role") != "admin":
        fail(f"{ADMIN_EMAIL} is not an admin account.")
    say(f"Signed in as {ADMIN_EMAIL}.")
    return res["token"]


# --------------------------------------------------------- 2. wait for models


def model_names(token):
    tags = api("GET", "/ollama/api/tags", token=token, timeout=30)
    names = set()
    for m in tags.get("models", []):
        name = m.get("model") or m.get("name") or ""
        names.add(name)
        if name.endswith(":latest"):
            names.add(name[: -len(":latest")])
    return names


def wait_for_models(token):
    needed = [CHAT_MODEL, EMBEDDING_MODEL]
    deadline = time.time() + MODEL_WAIT_MINUTES * 60
    announced = False
    while True:
        try:
            missing = [m for m in needed if m not in model_names(token)]
        except (ApiError, urllib.error.URLError, OSError) as e:
            missing, err = needed, e
        else:
            err = None
        if not missing:
            say(f"AI models ready: {', '.join(needed)}")
            return
        if time.time() > deadline:
            hint = f" Last error: {err}" if err else ""
            fail(
                f"Still waiting for {', '.join(missing)} after {MODEL_WAIT_MINUTES} minutes.{hint}\n"
                "  Check the download with: docker compose logs model-download"
            )
        if not announced:
            say(f"Waiting for AI models to finish downloading: {', '.join(missing)}")
            say("  (first run only; this can take a while. Progress: docker compose logs -f model-download)")
            announced = True
        time.sleep(15)


# --------------------------------------------------------------- 3. settings


def apply_settings(token):
    auth = api("GET", "/api/v1/auths/admin/config", token=token)
    # Creating the admin from .env switches sign-up off; staff need it on to request access.
    if not auth.get("ENABLE_SIGNUP") or auth.get("DEFAULT_USER_ROLE") != "pending":
        auth.update({"ENABLE_SIGNUP": True, "DEFAULT_USER_ROLE": "pending"})
        api("POST", "/api/v1/auths/admin/config", auth, token=token)
    say("Sign-up: on. New accounts wait for admin approval (Admin Panel > Users).")

    api("POST", "/api/v1/retrieval/config/update", {"RAG_TEMPLATE": RAG_TEMPLATE, "TOP_K": 5}, token=token)

    # Each of these is an extra AI call around every message. Keep only chat titles
    # so that answers from a local model stay quick.
    tasks = api("GET", "/api/v1/tasks/config", token=token)
    tasks.update(
        {
            "ENABLE_TITLE_GENERATION": True,
            "ENABLE_TAGS_GENERATION": False,
            "ENABLE_FOLLOW_UP_GENERATION": False,
            "ENABLE_AUTOCOMPLETE_GENERATION": False,
            "ENABLE_RETRIEVAL_QUERY_GENERATION": False,
            "ENABLE_SEARCH_QUERY_GENERATION": False,
        }
    )
    api("POST", "/api/v1/tasks/config/update", tasks, token=token)
    say("Document search: top 5 excerpts per question, one AI call per message.")

    emb = api("GET", "/api/v1/retrieval/embedding", token=token)
    if emb.get("RAG_EMBEDDING_ENGINE") != "ollama" or emb.get("RAG_EMBEDDING_MODEL") != EMBEDDING_MODEL:
        emb.update({"RAG_EMBEDDING_ENGINE": "ollama", "RAG_EMBEDDING_MODEL": EMBEDDING_MODEL})
        api("POST", "/api/v1/retrieval/embedding/update", emb, token=token, timeout=300)
        say(f"Document search model set to {EMBEDDING_MODEL}.")
        return True
    return False


# ------------------------------------------------------ 4. document library


def find_or_create_library(token):
    page, seen = 1, 0
    while True:
        res = api("GET", f"/api/v1/knowledge/?page={page}", token=token)
        items = res.get("items", [])
        for kb in items:
            if kb.get("name") == LIBRARY_NAME:
                return kb
        seen += len(items)
        if not items or seen >= res.get("total", 0):
            break
        page += 1
    kb = api(
        "POST",
        "/api/v1/knowledge/create",
        {"name": LIBRARY_NAME, "description": LIBRARY_DESCRIPTION, "access_grants": EVERYONE_CAN_READ},
        token=token,
    )
    say(f'Created the "{LIBRARY_NAME}" library.')
    return kb


def local_files():
    """Files under company-docs/, skipping hidden files and names starting with "_"."""
    files = []
    if not DOCS_DIR.is_dir():
        return files
    for path in sorted(DOCS_DIR.rglob("*")):
        rel = path.relative_to(DOCS_DIR)
        if not path.is_file() or any(p.startswith((".", "_", "~$")) for p in rel.parts):
            continue
        content = path.read_bytes()
        files.append(
            {
                "abs": path,
                "filename": path.name,
                "path": rel.parent.as_posix() if rel.parent.as_posix() != "." else "",
                "checksum": hashlib.sha256(content).hexdigest(),
                "size": len(content),
            }
        )
    return files


def upload_file(token, item):
    boundary = uuid.uuid4().hex
    content_type = CONTENT_TYPES.get(item["abs"].suffix.lower(), "application/octet-stream")
    safe_name = item["filename"].replace('"', "'")
    metadata = json.dumps({"file_hash": item["checksum"]})
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n{metadata}\r\n'
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{safe_name}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + item["abs"].read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    # Processed in the request, so the text is extracted and indexed once this returns.
    file_id = api(
        "POST",
        "/api/v1/files/?process=true&process_in_background=false",
        token=token,
        data=body,
        content_type=f"multipart/form-data; boundary={boundary}",
        timeout=3600,
    )["id"]
    if api("GET", f"/api/v1/files/{file_id}/process/status", token=token).get("status") == "failed":
        error = (api("GET", f"/api/v1/files/{file_id}", token=token).get("data") or {}).get("error")
        api("DELETE", f"/api/v1/files/{file_id}", token=token)
        raise ApiError(400, error or "could not extract any text")
    return file_id


def ensure_directories(token, kb_id, mkdir, directory_map):
    for dir_path in mkdir:
        parent, _, name = dir_path.rpartition("/")
        created = api(
            "POST",
            f"/api/v1/knowledge/{kb_id}/dirs/create",
            {"name": name, "parent_id": directory_map.get(parent) if parent else None},
            token=token,
        )
        directory_map[dir_path] = created["id"]


def sync_documents(token, kb):
    kb_id = kb["id"]
    files = local_files()
    if not DOCS_DIR.is_dir():
        say(f"No company-docs folder found at {DOCS_DIR}; skipping documents.")
        return 0, 0, []
    manifest = [{k: f[k] for k in ("filename", "path", "checksum", "size")} for f in files]
    diff = api("POST", f"/api/v1/knowledge/{kb_id}/sync/diff", {"manifest": manifest}, token=token)
    by_key = {(f["path"], f["filename"]): f for f in files}
    to_upload = diff["added"] + diff["modified"]
    stale = [m["stale_file_id"] for m in diff["modified"]] + [d["file_id"] for d in diff["deleted"]]

    say(
        f"Documents: {len(files)} in company-docs/, {diff['unmodified_count']} unchanged, "
        f"{len(diff['added'])} new, {len(diff['modified'])} changed, {len(diff['deleted'])} removed."
    )
    directory_map = dict(diff.get("directory_map") or {})
    ensure_directories(token, kb_id, diff.get("mkdir") or [], directory_map)

    failed = []
    for n, entry in enumerate(to_upload, 1):
        item = by_key[(entry["path"], entry["filename"])]
        label = f"{item['path']}/{item['filename']}" if item["path"] else item["filename"]
        say(f"  [{n}/{len(to_upload)}] Reading {label} ...")
        started = time.time()
        try:
            file_id = upload_file(token, item)
            api(
                "POST",
                f"/api/v1/knowledge/{kb_id}/file/add",
                {"file_id": file_id, "directory_id": directory_map.get(item["path"]) if item["path"] else None},
                token=token,
                timeout=3600,
            )
            say(f"         done in {time.time() - started:.0f}s")
        except ApiError as e:
            failed.append((label, str(e.detail)))
            say(f"         FAILED: {e.detail}")

    if stale or diff.get("rmdir"):
        api(
            "POST",
            f"/api/v1/knowledge/{kb_id}/sync/cleanup",
            {"file_ids": stale, "dir_ids": diff.get("rmdir") or []},
            token=token,
        )
    return len(files), len(to_upload) - len(failed), failed


# ------------------------------------------------------------ 5. assistants


def get_model(token, model_id):
    try:
        return api("GET", f"/api/v1/models/model?id={urllib.parse.quote(model_id)}", token=token)
    except ApiError as e:
        if e.status in (401, 404):
            return None
        raise


def register_base_model(token):
    """Staff can only use an assistant if they may also read its base model.
    Register the base model as readable by everyone but hidden from the model list."""
    form = {
        "id": CHAT_MODEL,
        "base_model_id": None,
        "name": CHAT_MODEL,
        "meta": {"hidden": True, "description": "AI model behind the assistants. Not for direct use."},
        "params": {},
        "access_grants": EVERYONE_CAN_READ,
        "is_active": True,
    }
    if get_model(token, CHAT_MODEL):
        api("POST", "/api/v1/models/model/update", form, token=token)
    else:
        api("POST", "/api/v1/models/create", form, token=token)


def parse_assistant(path):
    """Read an assistant file: a "---" header of key: value lines, then the instructions."""
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        fail(f"{path.name}: must start with a '---' header block (see the existing files).")
    header, body = text[4:].split("\n---\n", 1)
    spec = {"suggestions": []}
    for line in header.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            fail(f"{path.name}: header line '{line}' should look like 'key: value'.")
        key, value = key.strip().lower(), value.strip()
        if key == "suggestion":
            spec["suggestions"].append(value)
        else:
            spec[key] = value
    for required in ("id", "name"):
        if not spec.get(required):
            fail(f"{path.name}: the header needs an '{required}:' line.")
    spec["system"] = body.strip().replace("{COMPANY_NAME}", COMPANY_NAME)
    spec["uses_documents"] = spec.get("uses_documents", "no").lower() in ("yes", "true", "1")
    spec["temperature"] = float(spec.get("temperature", "0.5"))
    return spec


def upsert_assistant(token, spec, kb):
    meta = {
        "description": spec.get("description", ""),
        "suggestion_prompts": [{"content": s} for s in spec["suggestions"]],
        "tags": [{"name": "company"}],
    }
    if spec["uses_documents"]:
        meta["knowledge"] = [{"type": "collection", "id": kb["id"], "name": kb["name"]}]
    form = {
        "id": spec["id"],
        "base_model_id": CHAT_MODEL,
        "name": spec["name"],
        "meta": meta,
        "params": {
            "system": spec["system"],
            "temperature": spec["temperature"],
            # Search the documents on every message and give the results to the model.
            # More reliable with small local models than letting the model call search tools.
            "function_calling": "legacy",
        },
        "access_grants": EVERYONE_CAN_READ,
        "is_active": True,
    }
    if get_model(token, spec["id"]):
        api("POST", "/api/v1/models/model/update", form, token=token)
        return "updated"
    api("POST", "/api/v1/models/create", form, token=token)
    return "created"


def setup_assistants(token, kb):
    files = sorted(ASSISTANTS_DIR.glob("*.md"))
    if not files:
        fail(f"No assistant files found in {ASSISTANTS_DIR}")
    ids = []
    for path in files:
        spec = parse_assistant(path)
        action = upsert_assistant(token, spec, kb)
        docs = " (uses company documents)" if spec["uses_documents"] else ""
        say(f'  {action}: {spec["name"]}{docs}')
        ids.append(spec["id"])

    current = api("GET", "/api/v1/configs/models", token=token)
    default = DEFAULT_ASSISTANT if DEFAULT_ASSISTANT in ids else ids[0]
    current.update({"DEFAULT_MODELS": default, "MODEL_ORDER_LIST": ids})
    api("POST", "/api/v1/configs/models", current, token=token)
    return ids, default


# -------------------------------------------------------------------- main


def main():
    say("=== Company AI setup ===")
    wait_for_server()
    token = sign_in()
    wait_for_models(token)
    embedding_changed = apply_settings(token)

    kb = find_or_create_library(token)
    if embedding_changed and kb.get("id"):
        say("Re-indexing existing documents for the new search model ...")
        api("POST", "/api/v1/knowledge/reindex", token=token, timeout=3600)
    total, uploaded, failed = sync_documents(token, kb)

    register_base_model(token)
    say(f"Assistants (all using {CHAT_MODEL}):")
    ids, default = setup_assistants(token, kb)

    say("\n=== Done ===")
    say(f"Open {PUBLIC_URL} and sign in as {ADMIN_EMAIL}.")
    say(f"Library: {total} document(s), {uploaded} uploaded this run. Default assistant: {default}.")
    if failed:
        say(f"\n{len(failed)} document(s) could not be read:")
        for label, why in failed:
            say(f"  - {label}: {why}")
        say("  Scanned PDFs need text (run OCR first). See README > Troubleshooting.")
        sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except ApiError as e:
        fail(f"Open WebUI returned an error: {e}")
    except KeyboardInterrupt:
        fail("Stopped.")
