# ChatGPT2API 部署说明（主程序 + 注册引擎 双服务）

> 本文档描述 **chatgpt2api（主程序）+ gptGrok2api-py（注册引擎）** 的联合部署方式。
> 两个仓库**相互独立**，各自部署为独立服务，通过 Nginx 分流 + 定时同步协作。

## 给接手部署的 AI / 工程师

两个仓库都是**私有仓库**，克隆需要 GitHub 凭据：

- 主程序（本仓库）：`https://github.com/xiaomuclaw/chatgpt2api`
- 注册引擎：`https://github.com/xiaomuclaw/gptGrok2api-py`

```bash
git clone https://oauth2:<你的PAT>@github.com/xiaomuclaw/chatgpt2api.git /opt/chatgpt2api
git clone https://oauth2:<你的PAT>@github.com/xiaomuclaw/gptGrok2api-py.git /opt/gptgrok2api-py
```

按第一~七节执行即可。密钥、邮箱凭据、代理池**不在仓库里**，需向负责人索取。

---

## 一、架构总览

```
用户
 ├─ https://主域名            → chatgpt2api      (127.0.0.1:8001)
 │                                账号池 / 图片 / 工作台 / /v1 API
 └─ https://注册域名(子域)     → 注册引擎        (127.0.0.1:8010)
                                  注册控制台 / 邮箱池 / 代理池 / 注册机

后台：cron 每分钟把注册引擎新注册的账号同步进 chatgpt2api
```

| 服务 | 仓库 | 端口 | 职责 |
|---|---|---|---|
| 主程序 | `chatgpt2api` | 127.0.0.1:**8001** | 账号池、图片/工作台、`/v1/*` API |
| 注册引擎 | `gptGrok2api-py` | 127.0.0.1:**8010** | 账号注册（协议/指纹浏览器）、邮箱池、代理池 |
| 验证码旁路 | （py 仓库内） | 127.0.0.1:**8877** | captcha-solver，过 Cloudflare |
| 清障服务 | 外部镜像 | 容器名 `flaresolverr:8191` | FlareSolverr |

### 为什么是两个服务

- **chatgpt2api 不含注册功能**（源码中无 register 模块、无邮箱池）。
- **注册引擎**具备完整注册实现（协议 + 指纹浏览器双模式）。
- 二者账号格式兼容：注册引擎产出的 `{access_token, refresh_token, id_token, email, ...}` 可直接被 chatgpt2api 的 `POST /api/accounts` 接受。

### 控制台访问说明（重要）

| 功能 | 所在控制台 |
|---|---|
| 账号管理、图片、工作台、代理、监控 | **chatgpt2api**（主域名） |
| **启动注册、邮箱池、注册参数** | **注册引擎**（注册子域） |

两个控制台都是 hash 路由、静态资源用绝对路径 `/assets/`，**无法在同一域名下按路径共存**，因此注册引擎用**独立子域**访问。

---

## 二、前置依赖

| 依赖 | 说明 | 必需 |
|---|---|---|
| Docker + Compose v2 | ≥24 | 是 |
| Nginx | 反向代理 | 是 |
| **FlareSolverr** | 注册过 CF | 注册必需 |
| **代理池** | 住宅 IP，注册与收信使用 | 注册必需 |
| **Outlook 邮箱池** | `邮箱----密码----client_id----refresh_token` | 注册必需 |
| 域名 + 两个子域 + SSL | 主域 + 注册子域 | 是 |

---

## 三、部署主程序 chatgpt2api

```bash
cd /opt
git clone <本仓库URL> chatgpt2api
cd chatgpt2api
mkdir -p data

# 1) 创建 .env
# 2) 创建 config.json（内容 {}）
# 3) 创建 deploy.local.yml（固定端口）
# 4) 启动
docker compose -f docker-compose.yml -f deploy.local.yml up -d
```

### `.env`

```env
CHATGPT2API_AUTH_KEY=<管理员密钥，长随机串>
CHATGPT2API_PORT=8001
CHATGPT2API_BASE_URL=https://主域名
CHATGPT2API_THREAD_TOKENS=120
TZ=Asia/Shanghai
```

> 若沿用官方镜像：`CHATGPT2API_IMAGE=ghcr.io/yukkcat/chatgpt2api:latest`
> 若从本仓库源码构建：注释掉该变量，并在 compose 中改用 `build: .`

### `deploy.local.yml`

```yaml
services:
  app:
    container_name: chatgpt2api
    ports: !override
      - "127.0.0.1:8001:80"
    volumes: !override
      - ./data:/app/data
      - ./config.json:/app/config.json
```

> ⚠️ 官方 compose 默认端口是 **3000**，若宿主已有服务占用，务必用本文件 + `!override` 改到 8001。
> ⚠️ 官方 compose 挂载了 `chatgpt2api-runtime:/app` 具名卷，部署到固定目录时建议改为 `!override` 只挂 `data` 和 `config.json`，避免配置被卷覆盖。

---

## 四、部署注册引擎 gptGrok2api-py

```bash
cd /opt
git clone <注册引擎仓库URL> gptgrok2api-py
cd gptgrok2api-py
mkdir -p data logs

# 1) 创建 .env、deploy.local.yml
# 2) 创建 data/register.json（见第六节）
# 3) 启动注册引擎
docker compose -f docker-compose.yml -f deploy.local.yml up -d --build

# 4) 启动 captcha-solver
docker compose -f deploy/docker-compose.captcha-solver.yml up -d --build

# 5) 让 captcha-solver 接入注册引擎网络（用容器名互访）
docker network connect gptgrok2api-py_default chatgpt2api-captcha-solver
```

### `.env`

```env
CHATGPT2API_AUTH_KEY=<与主程序相同的管理员密钥>
CHATGPT2API_PORT=8010
CHATGPT2API_BASE_URL=https://注册子域
TZ=Asia/Shanghai
STORAGE_BACKEND=json
```

### `deploy.local.yml`

```yaml
services:
  app:
    container_name: gptgrok2api-py
    ports: !override
      - "127.0.0.1:8010:80"
    networks:
      default:
      grok2api_default:
        aliases:
          - gptgrok2api-py

networks:
  grok2api_default:
    external: true
    name: grok2api_default
```

> `grok2api_default` 网络用于让注册引擎访问 FlareSolverr（若你的 FlareSolverr 在别的网络，改为对应网络名）。

---

## 五、Nginx 配置

需要**两个 server 块**：主域名 → 主程序；注册子域 → 注册引擎。

### 主域名（chatgpt2api）

```nginx
server {
    server_name 主域名;
    client_max_body_size 200m;

    # 注册接口也走注册引擎（便于从任意控制台调用）
    location ^~ /api/register {
        proxy_pass http://127.0.0.1:8010;
        include /etc/nginx/snippets/proxy-common.conf;
    }

    location / {
        proxy_pass http://127.0.0.1:8001;
        include /etc/nginx/snippets/proxy-common.conf;
    }

    listen [::]:443 ssl;
    listen 443 ssl;
    ssl_certificate     /etc/letsencrypt/live/主域名/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/主域名/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}
server {
    if ($host = 主域名) { return 301 https://$host$request_uri; }
    listen 80;
    listen [::]:80;
    server_name 主域名;
    return 404;
}
```

### 注册子域（注册引擎控制台）

```nginx
server {
    server_name 注册子域;
    client_max_body_size 200m;

    location / {
        proxy_pass http://127.0.0.1:8010;
        include /etc/nginx/snippets/proxy-common.conf;
    }

    listen [::]:443 ssl;
    listen 443 ssl;
    ssl_certificate     /etc/letsencrypt/live/注册子域/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/注册子域/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}
server {
    if ($host = 注册子域) { return 301 https://$host$request_uri; }
    listen 80;
    listen [::]:80;
    server_name 注册子域;
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

签发证书：`certbot --nginx -d 主域名 -d 注册子域 --redirect`

---

## 六、注册配置 `data/register.json`（注册引擎侧）

通过注册引擎控制台（注册子域）保存。关键字段：

```json
{
  "target": "openai",
  "register_mode": "browser",
  "threads": 1,
  "task_interval_min": 15,
  "task_interval_max": 40,
  "proxy": "http://u:p@host:port\nhttp://u:p@host2:port2",
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
  "browser": {
    "api_base": "http://chatgpt2api-captcha-solver:8877",
    "request_timeout": 30,
    "captcha_timeout": 180
  }
}
```

要点：
- `register_mode`：`browser`（指纹浏览器，存活率高，推荐）或 `protocol`（快，但账号易被吊销）
- `threads` 浏览器模式**必须为 1**（CloakBrowser 免费版单会话；代码已自动钳制）
- `browser.api_base` 必须用**容器名**，不能用 `127.0.0.1`
- Outlook 别名：单邮箱上游上限 **2 个账号**（原始 + 1 别名），故 `alias_per_email: 1`
- `task_interval_min/max`：每个任务之间的随机延迟（秒），降低上游风控

---

## 七、账号同步（注册引擎 → chatgpt2api）

chatgpt2api 按凭据去重，但注册引擎独立刷新 token，直接全量导入会**重复**。因此先读主程序已有账号身份，只导入缺失的。

### `/opt/sync_to_chatgpt2api.py`

```python
#!/usr/bin/env python3
"""Sync accounts from the register engine into chatgpt2api (idempotent)."""
import json, os, sys, urllib.error, urllib.request

KEY = os.environ.get("C2A_ADMIN_KEY", "")
BASE = os.environ.get("C2A_BASE", "http://127.0.0.1:8001").rstrip("/")
SRC = os.environ.get("C2A_SRC", "/opt/gptgrok2api-py/data/accounts.json")

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
        print("read chatgpt2api accounts failed: %s" % exc, file=sys.stderr); return 1
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

### `/opt/sync_to_chatgpt2api.sh`

```sh
#!/bin/sh
C2A_ADMIN_KEY=<管理员密钥> exec python3 /opt/sync_to_chatgpt2api.py
```

### crontab（每分钟）

```bash
chmod +x /opt/sync_to_chatgpt2api.py /opt/sync_to_chatgpt2api.sh
( crontab -l 2>/dev/null | grep -v sync_to_chatgpt2api ; \
  echo "* * * * * /opt/sync_to_chatgpt2api.sh >> /var/log/c2a_sync.log 2>&1" ) | crontab -
```

---

## 八、验证部署

```bash
K=<管理员密钥>

# 1. 主程序
curl -s -o /dev/null -w "main:%{http_code}\n" http://127.0.0.1:8001/

# 2. 注册引擎（返回注册配置，非 503）
curl -s -H "Authorization: Bearer $K" http://127.0.0.1:8010/api/register | head -c 200

# 3. 注册引擎控制台
curl -s -o /dev/null -w "console:%{http_code}\n" http://127.0.0.1:8010/

# 4. 域名 API（主程序）
curl -s -X POST -H "Authorization: Bearer $K" -H "Content-Type: application/json" \
  -d '{"model":"gpt-5","messages":[{"role":"user","content":"hi"}]}' \
  https://主域名/v1/chat/completions

# 5. 同步
C2A_ADMIN_KEY=$K python3 /opt/sync_to_chatgpt2api.py
curl -s -H "Authorization: Bearer $K" "http://127.0.0.1:8001/api/accounts?page_size=500" | head -c 120
```

---

## 九、常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| 注册报 503 `executor is not configured` | 误用主程序注册 | 注册必须用注册引擎（8010） |
| 注册引擎控制台打不开 | 未暴露访问入口 | 用子域反代到 8010 |
| 主程序账号池重复 | 全量导入而非按身份比对 | 用第七节的同步脚本 |
| `browser.api_base` 连不上 | 用了 `127.0.0.1` | 改容器名 `chatgpt2api-captcha-solver:8877` |
| 浏览器模式注册失败/并发错 | CloakBrowser 单会话 | `threads=1`（代码已自动钳制） |
| 收不到验证码 | 上游拒发 | 代码自动换邮箱重试；检查邮箱 token |
| 注册后账号 401 | 账号被上游吊销 | 改用 `register_mode: browser` |
| 端口冲突 | 官方默认 3000 | `deploy.local.yml` + `!override` 改端口 |

---

## 十、两个仓库的分工与维护

| 仓库 | 改动内容 |
|---|---|
| **chatgpt2api** | 无需改动（直接用官方镜像或本仓库源码构建） |
| **gptGrok2api-py** | 含注册相关二次开发补丁（见其 `DEPLOY.md` 第十一节）：浏览器注册、代理/取码重试、邮箱切换、任务间隔 |

**升级注意**：注册引擎的补丁在 `services/register/`、`services/openai_browser_*.py`、`captcha-solver/openai_browser/`；升级上游时需保留。

### 数据迁移

```bash
# 源服务器
tar czf c2a-data.tgz /opt/chatgpt2api/data /opt/chatgpt2api/config.json \
                    /opt/gptgrok2api-py/data
# 目标服务器解包到对应目录
```

包含：主程序账号库（`data/chatgpt2api.db`）、注册引擎账号池、邮箱池凭据、代理池、注册配置。
