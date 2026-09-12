#!/usr/bin/env python3
"""Re-attach the iCloud + register-engine integration onto chatgpt2api.

WHY: this repo carries additions (iCloud privacy-mail page + sidecar, and the
GPTGrok2API register page talking to a separate register engine) on top of the
upstream chatgpt2api project.  When upstream releases a new version you merge
it in, which may revert the few upstream files we touch.  Run this afterwards
to put our additions back.

USAGE (after updating upstream):
    git fetch upstream && git merge upstream/main      # keep upstream on conflicts
    python3 integration/attach.py
    docker compose -f docker-compose.yml -f deploy.local.yml --profile local-icloud up -d --build

The script is idempotent: run it as often as you like.  If an anchor is missing
(upstream rewrote that file), it says so and exits non-zero so you can merge by
hand for that one file.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "integration", "assets")
failed = []


def log(msg):
    print(msg, flush=True)


def restore_assets():
    n = 0
    for dirpath, _dirs, files in os.walk(ASSETS):
        for name in files:
            src = os.path.join(dirpath, name)
            rel = os.path.relpath(src, ASSETS)
            dst = os.path.join(ROOT, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            n += 1
    log("[1/3] restored %d integration file(s)" % n)


def patch(rel, already, edits):
    path = os.path.join(ROOT, rel)
    if not os.path.isfile(path):
        log("      !! %s missing" % rel)
        failed.append(rel)
        return
    s = open(path, encoding="utf-8").read()
    if all(marker in s for marker in already):
        log("      %s: already applied" % rel)
        return
    for anchor, replacement in edits:
        if anchor not in s:
            log("      !! %s: anchor not found -> merge by hand" % rel)
            log("         missing anchor: %s" % anchor.strip().splitlines()[0][:80])
            failed.append(rel)
            return
        s = s.replace(anchor, replacement, 1)
    open(path, "w", encoding="utf-8").write(s)
    log("      %s: patched" % rel)


def patch_backend():
    log("[2/3] patching backend / compose / frontend wiring")
    patch(
        "api/app.py",
        ["icloud_privacy_mail"],
        [
            (
                "from api import accounts, ai, image_tasks, prompts, system",
                "from api import accounts, ai, icloud_privacy_mail, image_tasks, prompts, system",
            ),
            (
                "    app.include_router(accounts.create_router())\n",
                "    app.include_router(accounts.create_router())\n"
                "    app.include_router(icloud_privacy_mail.create_router())\n",
            ),
        ],
    )
    patch(
        "web-vue/src/router/routes.ts",
        ["path: 'register'", "path: 'icloud'"],
        [
            (
                "      {\n        path: 'accounts',\n        name: 'accounts',",
                "      {\n        path: 'register',\n        name: 'register',\n"
                "        component: () => import('@/views/Register.vue'),\n"
                "        meta: { requiredCapability: 'admin_console' },\n"
                "      },\n"
                "      {\n        path: 'accounts',\n        name: 'accounts',",
            ),
            (
                "      {\n        path: 'settings',\n        name: 'settings',",
                "      {\n        path: 'icloud',\n        name: 'icloud',\n"
                "        component: () => import('@/views/ICloudPrivacyMail.vue'),\n"
                "        meta: { requiredCapability: 'admin_console', management: true },\n"
                "      },\n"
                "      {\n        path: 'settings',\n        name: 'settings',",
            ),
        ],
    )
    patch(
        "web-vue/src/layouts/AppShell.vue",
        ["path: '/register'", "path: '/icloud'"],
        [
            (
                "  {\n    path: '/logs',\n    label: '日志管理',",
                "  {\n    path: '/register',\n    label: '注册账号',\n"
                "    icon: 'M12 2a5 5 0 1 1 0 10A5 5 0 0 1 12 2zm0 12c2.8 0 5.2 1.4 6.3 3.5l-1.7 1c-.8-1.5-2.6-2.5-4.6-2.5s-3.8 1-4.6 2.5l-1.7-1C6.8 15.4 9.2 14 12 14zm7-1v3h3v2h-3v3h-2v-3h-3v-2h3v-3h2z',\n"
                "    capability: 'admin_console',\n"
                "  },\n"
                "  {\n    path: '/icloud',\n    label: 'iCloud 邮箱',\n"
                "    icon: 'M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zm0 2v.4l8 5 8-5V6H4zm16 12V8.8l-7.4 4.6a1 1 0 0 1-1.2 0L4 8.8V18h16z',\n"
                "    capability: 'admin_console',\n"
                "  },\n"
                "  {\n    path: '/logs',\n    label: '日志管理',",
            ),
            (
                "  settings: '系统设置',",
                "  settings: '系统设置',\n  register: '注册账号',\n  icloud: 'iCloud 邮箱',",
            ),
            (
                "  '/proxy': () => import('@/views/Proxy.vue'),",
                "  '/proxy': () => import('@/views/Proxy.vue'),\n"
                "  '/register': () => import('@/views/Register.vue'),\n"
                "  '/icloud': () => import('@/views/ICloudPrivacyMail.vue'),",
            ),
        ],
    )
    patch(
        "docker-compose.yml",
        ["icloud-privacy-mail:"],
        [
            (
                "services:\n  app:",
                "services:\n"
                "  icloud-privacy-mail:\n"
                "    profiles: [\"local-icloud\"]\n"
                "    build:\n"
                "      context: .\n"
                "      dockerfile: deploy/icloud-privacy-mail/Dockerfile\n"
                "    image: ${ICLOUD_PRIVACY_MAIL_IMAGE:-chatgpt2api/icloud-privacy-mail:local}\n"
                "    container_name: chatgpt2api-icloud-privacy-mail\n"
                "    restart: unless-stopped\n"
                "    environment:\n"
                "      IPM_API_KEY: ${ICLOUD_PRIVACY_MAIL_API_KEY:-}\n"
                "      IPM_PUBLIC_BASE_URL: ${ICLOUD_PRIVACY_MAIL_PUBLIC_BASE_URL:-http://icloud-privacy-mail:8787}\n"
                "      IPM_UPDATE_ENABLED: \"false\"\n"
                "      HTTP_PROXY: ${ICLOUD_PRIVACY_MAIL_HTTP_PROXY:-}\n"
                "      HTTPS_PROXY: ${ICLOUD_PRIVACY_MAIL_HTTPS_PROXY:-}\n"
                "      NO_PROXY: ${ICLOUD_PRIVACY_MAIL_NO_PROXY:-127.0.0.1,localhost,icloud-privacy-mail}\n"
                "      TZ: ${TZ:-Asia/Shanghai}\n"
                "    volumes:\n"
                "      - ./data/icloud-privacy-mail:/data\n"
                "    healthcheck:\n"
                "      test: [\"CMD-SHELL\", \"wget -qO- http://127.0.0.1:8787/login >/dev/null || exit 1\"]\n"
                "      interval: 15s\n"
                "      timeout: 5s\n"
                "      retries: 10\n"
                "      start_period: 10s\n\n"
                "  app:",
            ),
            (
                "      CHATGPT2API_THREAD_TOKENS: ${CHATGPT2API_THREAD_TOKENS:-120}\n",
                "      CHATGPT2API_THREAD_TOKENS: ${CHATGPT2API_THREAD_TOKENS:-120}\n"
                "      ICLOUD_PRIVACY_MAIL_BASE_URL: ${ICLOUD_PRIVACY_MAIL_BASE_URL:-http://icloud-privacy-mail:8787}\n",
            ),
        ],
    )


def regen_icons():
    log("[3/3] regenerating lucide icon set (needs docker + network)")
    src = os.path.join(ROOT, "web-vue")
    with tempfile.TemporaryDirectory() as tmp:
        dst = os.path.join(tmp, "web-vue")
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("node_modules", "dist"))
        cmd = (
            "npm ci --silent >/dev/null 2>&1 && npm run icons:generate >/dev/null 2>&1"
        )
        r = subprocess.run(
            ["docker", "run", "--rm", "-v", dst + ":/app", "-w", "/app", "node:22-alpine", "sh", "-c", cmd],
            capture_output=True, text=True,
        )
        out = os.path.join(dst, "src", "lib", "localLucideIcons.generated.ts")
        if r.returncode != 0 or not os.path.isfile(out):
            log("      !! icon regeneration failed; kept existing generated file")
            log("         %s" % (r.stderr or r.stdout or "").strip()[:200])
            return
        shutil.copy2(out, os.path.join(src, "src", "lib", "localLucideIcons.generated.ts"))
        log("      icons regenerated")


def main():
    if not os.path.isdir(ASSETS):
        log("integration/assets missing")
        return 1
    restore_assets()
    patch_backend()
    regen_icons()
    if failed:
        log("\nDONE WITH WARNINGS — merge by hand for: %s" % ", ".join(sorted(set(failed))))
        return 1
    log("\nDONE — integration attached. Rebuild with:")
    log("  docker compose -f docker-compose.yml -f deploy.local.yml --profile local-icloud up -d --build")
    return 0


if __name__ == "__main__":
    sys.exit(main())
