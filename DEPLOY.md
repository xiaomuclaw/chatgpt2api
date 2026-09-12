# 部署说明（ChatGPT2API 主程序 + 注册引擎 + iCloud 邮箱）

> 本文档描述**完整功能部署**：主控制台、内嵌注册页、iCloud 隐私邮箱。
> 照本文档执行即可一次性部署完成。

## 给接手部署的 AI / 工程师（先读这段）

**需要两个仓库，缺一不可**：

| 仓库 | 可见性 | 提供什么 |
|---|---|---|
| `https://github.com/xiaomuclaw/chatgpt2api` | **公开** | 主程序：控制台、账号池、图片、**iCloud 邮箱（自包含）**、**注册页前端（内嵌）** |
| `https://github.com/xiaomuclaw/gptGrok2api-py` | **私有** | **注册后端**：注册机、邮箱池、代理池、captcha-solver |

> ⚠️ 第二个仓库是**私有**的，克隆需要 GitHub 凭据（PAT 或 SSH key）。没有凭据时，主程序可部署（含 iCloud），但**注册功能不可用**。

```bash
git clone https://oauth2:<PAT>@github.com/xiaomuclaw/chatgpt2api.git /opt/chatgpt2api
git clone https://oauth2:<PAT>@github.com/xiaomuclaw/gptGrok2api-py.git /opt/chatgpt2api/register-engine
```

按第一~八节执行。密钥、邮箱凭据、代理池**不在仓库里**，需向负责人索取。

---

## 一、架构总览

```
用户 → https://主域名
        │
     Nginx
        ├─ /register/    → 注册引擎独立控制台   (127.0.0.1:8012)
        ├─ /api/register*→ 注册引擎后端         (127.0.0.1:8012)  ← 内嵌注册页也走这里
        └─ 其余全部       → 主程序              (127.0.0.1:3000)
                              │
              主程序内置页面：概览/账号/图片/iCloud 邮箱/注册账号(内嵌)
```

| 服务 | 仓库 | 端口 | 职责 |
|---|---|---|---|
| 主程序 | `chatgpt2api` | 127.0.0.1:**3000** | 控制台、账号池、图片、`/v1/*` API |
| **iCloud sidecar** | 同上（**自包含**） | 容器名 `icloud-privacy-mail:8787` | Apple 登录、Hide My Email、收验证码 |
| 注册引擎 | `gptGrok2api-py` | 127.0.0.1:**8012** | 注册机、邮箱池、代理池 |
| 注册用 captcha-solver | 同上（仓库内） | 127.0.0.1:**8879** | 浏览器过 Cloudflare |

**关键**：注册页**前端**已内嵌进主程序（`web-vue/src/views/Register.vue`），
但它的**后端**是注册引擎。所以内嵌页面需要注册引擎在跑。

---

## 二、前置依赖

| 依赖 | 说明 | 必需 |
|---|---|---|
| Docker + Compose v2 | ≥24 | 是 |
| Nginx + 域名 + SSL | certbot 可签发 | 是 |
| FlareSolverr | 过 CF 挑战 | 注册必需 |
| 代理池 | 住宅 IP（HTTP 代理，每行一个） | 注册必需 |
| Outlook 邮箱池 | `邮箱----密码----client_id----refresh_token` | 注册必需 |

---

## 三、部署主程序（含 iCloud）

```bash
cd /opt
git clone <chatgpt2api 地址> chatgpt2api      # 或 clone 到 /opt/chatgpt2api
cd chatgpt2api
mkdir -p data
printf '{}\n' > config.json
```

### `.env`

```env
CHATGPT2API_AUTH_KEY=<管理员密钥，长随机串>
CHATGPT2API_PORT=3000
CHATGPT2API_BASE_URL=https://你的域名
CHATGPT2API_THREAD_TOKENS=120
TZ=Asia/Shanghai
# iCloud 隐私邮箱 sidecar
ICLOUD_PRIVACY_MAIL_BASE_URL=http://icloud-privacy-mail:8787
ICLOUD_PRIVACY_MAIL_API_KEY=<随机密钥>
ICLOUD_PRIVACY_MAIL_PUBLIC_BASE_URL=http://127.0.0.1:8788
ICLOUD_PRIVACY_MAIL_NO_PROXY=127.0.0.1,localhost,icloud-privacy-mail,.apple.com,.icloud.com,.apple.com.cn,.icloud.com.cn
```

### `deploy.local.yml`（**必须创建**，仓库中不含）

```yaml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    image: chatgpt2api:local
    container_name: chatgpt2api
    ports: !override
      - "127.0.0.1:3000:80"
    volumes: !override
      - ./data:/app/data
      - ./config.json:/app/config.json
```

> 官方 compose 默认用官方镜像 + 具名卷挂 `/app`，会把代码盖住。本文件改为**源码构建**并只挂数据，
> 这样仓库里的 iCloud / 内嵌注册页才生效。`!override` 必须保留。

### 启动

```bash
docker network create chatgpt2api_default 2>/dev/null || true
docker compose -f docker-compose.yml -f deploy.local.yml --profile local-icloud up -d --build
```

> 不加 `--profile local-icloud` 时 iCloud sidecar 不启动，iCloud 页面显示"模块不可用"。

---

## 四、部署注册引擎

```bash
cd /opt/chatgpt2api
git clone <gptGrok2api-py 地址> register-engine
cd register-engine
mkdir -p data logs

# 复制注册配置（邮箱池 + 代理池 + 注册参数），向负责人索取 data/register.json
# 放到 register-engine/data/register.json
```

### `.env`

```env
CHATGPT2API_AUTH_KEY=<与主程序相同的管理员密钥>
CHATGPT2API_PORT=8012
CHATGPT2API_BASE_URL=https://你的域名/register
TZ=Asia/Shanghai
STORAGE_BACKEND=json
```

### `deploy.local.yml`（**必须创建**）

```yaml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        WEB_BASE_PATH: /register/
        WEB_API_BASE: /register
    image: register-engine:local
    container_name: register-engine
    ports: !override
      - "127.0.0.1:8012:80"
    networks:
      default:
      chatgpt2api_default:
        aliases:
          - register-engine

networks:
  chatgpt2api_default:
    external: true
    name: chatgpt2api_default
```

> `WEB_BASE_PATH=/register/` 让控制台静态资源挂在 `/register/` 下，配合 nginx 路径剥离。

### `deploy.captcha.yml`（**必须创建**，注册引擎专用 solver）

```yaml
services:
  captcha-solver:
    container_name: register-captcha-solver
    ports: !override
      - "127.0.0.1:8879:8877"
    networks:
      default:
      chatgpt2api_default:
        aliases:
          - register-captcha-solver

networks:
  chatgpt2api_default:
    external: true
    name: chatgpt2api_default
```

### 启动

```bash
docker compose -f docker-compose.yml -f deploy.local.yml up -d --build
docker compose -f deploy/docker-compose.captcha-solver.yml -f deploy.captcha.yml up -d --build
```

---

## 五、Nginx 配置

```nginx
server {
    server_name 你的域名;
    client_max_body_size 200m;

    # 内嵌注册页的后端接口 -> 注册引擎
    location ^~ /api/register {
        proxy_pass http://127.0.0.1:8012;
        include /etc/nginx/snippets/proxy-common.conf;
    }

    # 注册引擎独立控制台（路径剥离）
    location = /register { return 301 /register/; }
    location ^~ /register/ {
        proxy_pass http://127.0.0.1:8012/;
        include /etc/nginx/snippets/proxy-common.conf;
    }

    # 其余 -> 主程序
    location / {
        proxy_pass http://127.0.0.1:3000;
        include /etc/nginx/snippets/proxy-common.conf;
    }

    listen [::]:443 ssl;
    listen 443 ssl;
    ssl_certificate     /etc/letsencrypt/live/你的域名/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/你的域名/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}
server {
    if ($host = 你的域名) { return 301 https://$host$request_uri; }
    listen 80;
    listen [::]:80;
    server_name 你的域名;
    return 404;
}
```

### `/etc/nginx/snippets/proxy-common.conf`

```
proxy_http_version 1.1;
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;
proxy_buffering off;
proxy_request_buffering off;
```

签发证书：`certbot --nginx -d 你的域名 --redirect`

---

## 六、注册配置 `register-engine/data/register.json`

关键字段（完整格式见 gptGrok2api-py 仓库的 DEPLOY.md）：

```json
{
  "target": "openai",
  "register_mode": "browser",
  "threads": 1,
  "task_interval_min": 30,
  "task_interval_max": 60,
  "proxy": "http://u:p@host:port\n...",
  "mail": {
    "providers": [{
      "id": "outlook-pool",
      "type": "outlook_token",
      "enable": true,
      "mode": "auto",
      "imap_host": "outlook.office365.com",
      "message_limit": 10,
      "alias_enabled": true,
      "alias_per_email": 1,
      "alias_prefix": "xmxcode2",
      "alias_include_original": true,
      "mailboxes": "email----password----client_id----refresh_token\n..."
    }],
    "api_use_register_proxy": true
  },
  "browser": { "api_base": "http://register-captcha-solver:8877" }
}
```

**要点**：
- `register_mode`：`browser`（指纹浏览器，存活率高）或 `protocol`（快但易被吊销）
- `threads` 浏览器模式**必须为 1**（代码已自动钳制）
- `browser.api_base` 用**容器名** `register-captcha-solver:8877`
- Outlook 单邮箱上游上限 **2 个账号**（原始 + 1 别名），故 `alias_per_email: 1`
- `task_interval_min/max`：任务间随机延迟（秒）。**建议 30-60 秒**，太密会触发上游限流

---

## 七、账号同步（注册引擎 → 主程序）

注册引擎产出账号后，需同步进主程序才能被 `/v1` 使用。

### `/opt/chatgpt2api/sync_register_to_c2a.py`

```python
#!/usr/bin/env python3
"""Sync accounts from the register engine into chatgpt2api (idempotent)."""
import json, os, sys, urllib.error, urllib.request

KEY = os.environ.get("C2A_ADMIN_KEY", "")
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
    if not KEY:
        print("C2A_ADMIN_KEY not set", file=sys.stderr); return 2
    accounts = [a for a in load_local() if isinstance(a, dict)]
    if not accounts:
        return 0
    try:
        have = existing()
    except Exception as exc:
        print("read main accounts failed: %s" % exc, file=sys.stderr); return 1
    missing = [a for a in accounts if identity(a) not in have]
    if not missing:
        return 0
    body = json.dumps({"accounts": missing}).encode()
    req = urllib.request.Request(BASE + "/api/accounts", data=body, method="POST", headers=headers())
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            d = json.load(resp)
    except urllib.error.HTTPError as exc:
        print("import HTTP %s: %s" % (exc.code, exc.read().decode()[:300]), file=sys.stderr); return 1
    except Exception as exc:
        print("import failed: %s" % exc, file=sys.stderr); return 1
    added = d.get("added")
    if added:
        print("synced %s new account(s)" % added)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

### 安装 cron（每分钟同步）

```bash
cat > /opt/chatgpt2api/sync.sh <<'SH'
#!/bin/sh
C2A_ADMIN_KEY=<管理员密钥> exec python3 /opt/chatgpt2api/sync_register_to_c2a.py
SH
chmod +x /opt/chatgpt2api/sync.sh
( crontab -l 2>/dev/null | grep -v sync_register_to_c2a ; \
  echo "* * * * * /opt/chatgpt2api/sync.sh >> /var/log/c2a_sync.log 2>&1" ) | crontab -
```

---

## 八、验证部署

```bash
K=<管理员密钥>

# 1. 主控制台
curl -s -o /dev/null -w "main:%{http_code}\n" https://你的域名/

# 2. 内嵌注册页（前端）
curl -s -o /dev/null -w "register-page:%{http_code}\n" "https://你的域名/#/register"

# 3. 注册后端（返回注册配置，不是 503）
curl -s -H "Authorization: Bearer $K" https://你的域名/api/register | head -c 200

# 4. 注册引擎独立控制台
curl -s -o /dev/null -w "register-console:%{http_code}\n" https://你的域名/register/

# 5. iCloud 代理
curl -s -H "Authorization: Bearer $K" https://你的域名/api/icloud/bridge-status

# 6. 账号同步
C2A_ADMIN_KEY=$K python3 /opt/chatgpt2api/sync_register_to_c2a.py

# 7. API 调用
curl -s -X POST -H "Authorization: Bearer $K" -H "Content-Type: application/json" \
  -d '{"model":"gpt-5","messages":[{"role":"user","content":"hi"}]}' \
  https://你的域名/v1/chat/completions
```

---

## 九、常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| iCloud 页显示"模块不可用" | sidecar 未启动 | 启动命令加 `--profile local-icloud` |
| 内嵌注册页空白/报错 | 注册引擎未跑 | 部署并启动 register-engine（8012） |
| 注册报 503 `executor is not configured` | 后端指向了主程序 | 确认 nginx `/api/register` 转发到 8012 |
| 注册页样式错乱 | 静态资源 404 | 确认注册引擎用 `WEB_BASE_PATH=/register/` 构建 |
| 主程序页面无「注册账号」 | 用了官方镜像 | 用 `deploy.local.yml` 源码构建 |
| 收不到验证码 | 上游限流（邮箱本身可读） | 拉长 `task_interval`；代码会自动换邮箱重试 |
| 注册后账号 401 | 账号被吊销 | 改用 `register_mode: browser` |
| 账号不进主程序 | 同步未跑 | 检查 cron 与 `sync_register_to_c2a.py` |

---

## 十、更新升级

见同仓库 **`UPDATE.md`**。要点：

```bash
# 主程序
cd /opt/chatgpt2api && git pull origin main
docker compose -f docker-compose.yml -f deploy.local.yml --profile local-icloud up -d --build

# 注册引擎
cd /opt/chatgpt2api/register-engine && git pull origin main
docker compose -f docker-compose.yml -f deploy.local.yml up -d --build
docker compose -f deploy/docker-compose.captcha-solver.yml -f deploy.captcha.yml up -d --build
```

`data/`、`config.json`、`deploy.local.yml`、`register-engine/` 均在 `.gitignore`，pull 不会覆盖。

---

## 十一、数据迁移

`data/` 不在 git 中，迁移时打包拷贝：

```bash
tar czf gpt-data.tgz \
    /opt/chatgpt2api/data \
    /opt/chatgpt2api/config.json \
    /opt/chatgpt2api/register-engine/data
```

含：主程序账号库（`data/chatgpt2api.db`）、注册引擎账号池、邮箱池凭据、代理池、注册配置、
iCloud 登录态（`data/icloud-privacy-mail/`）。
