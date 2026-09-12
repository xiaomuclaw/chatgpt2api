#!/usr/bin/env python3
"""Sync accounts from the dedicated register engine into chatgpt2api.

Idempotent: reads chatgpt2api's current identities first and only posts the
missing ones (keyed on user_id, else email), because token refresh on either
side would otherwise look like a new account.
"""
import json
import os
import sys
import urllib.error
import urllib.request

KEY = os.environ.get("C2A_ADMIN_KEY", "gpt2api-E302586413A6E867C897CC4E4A72D32B7DAEDC5B26FD9192")
BASE = os.environ.get("C2A_BASE", "http://127.0.0.1:3000").rstrip("/")
SRC = os.environ.get("C2A_SRC", "/opt/chatgpt2api/register-engine/data/accounts.json")


def headers():
    return {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}


def load_local():
    try:
        with open(SRC, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        return []
    return d.get("items", d) if isinstance(d, dict) else d


def identity(a):
    uid = str(a.get("user_id") or "").strip()
    return ("uid:" + uid) if uid else ("mail:" + str(a.get("email") or "").strip().lower())


def existing():
    req = urllib.request.Request(BASE + "/api/accounts?page_size=500", headers=headers())
    with urllib.request.urlopen(req, timeout=30) as resp:
        d = json.load(resp)
    items = d.get("items", d) if isinstance(d, dict) else d
    return {identity(a) for a in items if isinstance(a, dict)}


def main():
    accounts = [a for a in load_local() if isinstance(a, dict)]
    if not accounts:
        return 0
    try:
        have = existing()
    except Exception as exc:
        print("read chatgpt2api accounts failed: %s" % exc, file=sys.stderr)
        return 1
    missing = [a for a in accounts if identity(a) not in have]
    if not missing:
        return 0
    body = json.dumps({"accounts": missing}).encode()
    req = urllib.request.Request(BASE + "/api/accounts", data=body, method="POST", headers=headers())
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            d = json.load(resp)
    except urllib.error.HTTPError as exc:
        print("import HTTP %s: %s" % (exc.code, exc.read().decode()[:300]), file=sys.stderr)
        return 1
    except Exception as exc:
        print("import failed: %s" % exc, file=sys.stderr)
        return 1
    added = d.get("added")
    if added:
        print("synced %s new account(s)" % added)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
