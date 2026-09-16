# 更新升级说明（gpt.xmxcode.com 部署）

## 升级只需三条命令（推荐）

```bash
cd /opt/chatgpt2api
git fetch upstream && git merge upstream/main          # 合并上游新版
python3 integration/attach.py                          # 一键贴回 iCloud + 注册页
docker compose -f docker-compose.yml -f deploy.local.yml --profile local-icloud up -d --build
```

`attach.py` 是幂等的：已打过补丁就跳过；若上游改动过大导致锚点找不到，会明确指出
**哪个文件需手工合并**并以非 0 退出（不会静默出错）。详见 `integration/README.md`。

> 注册引擎是**独立仓库**，单独 `git pull` 升级即可；注册逻辑全在后端，
> 后端升级**无需**重新同步内嵌页。

---



> **推荐用集成包自动重新贴回**：本项目相对上游的增补（iCloud + 注册页）已整理进
> `integration/`，上游升级后执行 **`python3 integration/attach.py`** 即可自动补回，
> 无需手工合并。详见 `integration/README.md`。下面是手工流程，供参考/排障。


本部署由**两个独立 git 仓库**组成，升级时各自独立拉取，**不需要再合并**。

| 目录 | 仓库 | 说明 |
|---|---|---|
| `/opt/chatgpt2api` | `xiaomuclaw/chatgpt2api` | 主程序（含 iCloud + 内嵌注册页） |
| `/opt/chatgpt2api/register-engine` | `xiaomuclaw/gptGrok2api-py` | 注册引擎（注册后端 + 独立控制台） |

---

## 一、升级主程序（chatgpt2api）

### 前置：先同步 fork
你的 fork 需要先从上游同步（GitHub 网页点 "Sync fork"，或本地）：

```bash
cd /opt/chatgpt2api
git remote add upstream https://github.com/yukkcat/chatgpt2api.git 2>/dev/null
git fetch upstream --tags
git merge upstream/main        # 有冲突则手动解决（见下）
git push origin main           # 把你的 fork 更新推回自己仓库
```

### 部署更新
```bash
cd /opt/chatgpt2api
git pull origin main
docker compose -f docker-compose.yml -f deploy.local.yml --profile local-icloud up -d --build
```

> `data/`、`config.json`、`deploy.local.yml`、`register-engine/` 都在 `.gitignore` 中，
> **pull 不会覆盖它们**，账号数据安全。

### 可能的冲突点（你改过的文件）
如果上游也改了这些文件，会冲突，需手动合并：

| 文件 | 你加的改动 |
|---|---|
| `api/app.py` | 注册 iCloud 路由 |
| `api/icloud_privacy_mail.py` | 新增（不会冲突） |
| `web-vue/src/layouts/AppShell.vue` | 侧边栏「注册账号」+「iCloud 邮箱」，外部链接支持 |
| `web-vue/src/router/routes.ts` | `/register`、`/icloud` 路由 |
| `docker-compose.yml` | iCloud sidecar 服务 |
| `web-vue/src/**`（16 个新文件） | 注册页整套（不会冲突） |

---

## 二、升级注册引擎（register-engine）

```bash
cd /opt/chatgpt2api/register-engine
git pull origin main
docker compose -f docker-compose.yml -f deploy.local.yml up -d --build
docker compose -f deploy/docker-compose.captcha-solver.yml -f deploy.captcha.yml up -d --build
```

> 注册引擎**不需要"再合并一次"**——它独立运行。你之前担心的"合并"，
> 指的是把注册页**前端**复制进 chatgpt2api 这件事，那**是一次性的**，已经完成并提交
> （在 chatgpt2api 仓库的 `web-vue/src/views/Register.vue` 等 16 个文件里），后续升级不需重做。

### 唯一需要注意的例外
如果注册引擎升级**改动了前端页面**（`web-vue/src/views/Register.vue` 等），
而你又希望 chatgpt2api 里**内嵌的注册页**也跟着变，才需要重新同步那 16 个文件：

```bash
SRC=/opt/chatgpt2api/register-engine/web-vue/src
DST=/opt/chatgpt2api/web-vue/src
# 重新复制注册页依赖闭包（见 DEPLOY.md 的列表），然后重建主程序
```

**但注册逻辑（注册机、邮箱池、代理、重试）全在后端**，后端升级不需要重同步前端，
内嵌页面照常工作（它调用的还是同一套 `/api/register*` 接口）。

---

## 三、仅供记录：部署时的关键配置

| 项 | 值 |
|---|---|
| 主程序端口 | 127.0.0.1:3000（nginx: gpt.xmxcode.com） |
| 注册引擎端口 | 127.0.0.1:8012（nginx: `/register/` 与 `/api/register*`） |
| iCloud sidecar | 容器名 `icloud-privacy-mail:8787`（不暴露宿主端口） |
| 专用 captcha-solver | 127.0.0.1:8879 |
| 账号同步 | cron 每分钟 `/opt/sync_register_to_c2a.py` |
| 管理密钥 | 见 `/opt/chatgpt2api/.env` 的 `CHATGPT2API_AUTH_KEY` |

---

## 四、注意事项

1. **git push 需要凭据**：服务器未存 GitHub token。推送时用
   `git push https://oauth2:<PAT>@github.com/...`，或先在服务器配置凭据助手。
2. **备份数据**：升级前建议
   `tar czf /root/backup-$(date +%F).tgz /opt/chatgpt2api/data /opt/chatgpt2api/config.json /opt/chatgpt2api/register-engine/data`
3. **浅克隆**：两个仓库都是浅克隆（历史不全），如需完整历史先 `git fetch --unshallow`。

---

## 务必保留：iCloud 代理出口配置（.env）

`.env` 不在 Git 仓库里（含密钥），**升级不会自动带来这几行，也不能丢**。
少了它们，Apple 协议登录会全部失败——Apple 对数据中心 IP 的认证端点直接
返回 HTTP 503，表现为「Apple 登录失败」或「iCloud 模块暂不可用」。

`/opt/chatgpt2api/.env` 必须包含（代理端口以 proxyhub 实际可用为准）：

```bash
ICLOUD_PRIVACY_MAIL_NO_PROXY=127.0.0.1,localhost,icloud-privacy-mail
# Apple 认证拒绝数据中心 IP，必须经住宅代理出口
IPM_PROXY_URLS=http://pool:<密码>@172.17.0.1:17026,http://pool:<密码>@172.17.0.1:17021,...
ICLOUD_PRIVACY_MAIL_HTTP_PROXY=http://pool:<密码>@172.17.0.1:17026
ICLOUD_PRIVACY_MAIL_HTTPS_PROXY=http://pool:<密码>@172.17.0.1:17026
```

要点：

- `IPM_PROXY_URLS` 是**逗号分隔的代理池**，sidecar 每次建连随机取一个。
  代理池单端口可用性约 85%，写多个端口才能容忍坏节点。
- `NO_PROXY` **不要**包含 `.apple.com` / `.icloud.com`，否则 Apple 流量会绕过
  代理直连，重新触发 503。
- 更换代理池后需要重建 sidecar：
  ```bash
  docker compose -f docker-compose.yml -f deploy.local.yml --profile local-icloud up -d --build icloud-privacy-mail
  ```
- 实测某端口是否可用于 Apple：
  ```bash
  curl -s -o /dev/null -w '%{http_code}\n' -x 'http://pool:<密码>@172.17.0.1:<端口>' \
    -X POST https://idmsa.apple.com/appleauth/auth/signin/init \
    -H 'Content-Type: application/json' -d '{"accountName":"t@e.com","rememberMe":false}'
  # 302/400 = 可用；503/000 = 不可用
  ```

---

## 两个必查项：HME 转发目标 与 账号同步

### 1. Hide My Email 的转发目标必须指向主号

Apple 的隐私邮箱有个**全账号转发目标**。如果它指向外部邮箱（例如 QQ 邮箱），
新建别名收到的邮件会被转到那里，本机 IMAP 永远取不到验证码，注册流程表现为
`等待注册验证码超时`。

查当前目标（会列出可选地址，`type=profile` 的即主号）：

```bash
python3 - <<'PY'
import json, urllib.request
s = json.load(open("/opt/chatgpt2api/data/icloud-privacy-mail/state.json"))["icloud_session"]
ls = next(x for x in s["login_states"] if x.get("kind") == "apple_account")
ck = ls["cookies"] if isinstance(ls["cookies"], str) else "; ".join(
    "%s=%s" % (c.get("name"), c.get("value")) for c in ls["cookies"])
req = urllib.request.Request("https://appleid.apple.com/account/manage/forwardemail")
for k, v in (("User-Agent", ls["user_agent"]), ("X-Apple-Api-Key", ls["api_key"]),
             ("scnt", ls["scnt"]), ("X-Apple-ID-Session-Id", ls.get("session_id", "")),
             ("Cookie", ck)):
    req.add_header(k, v)
if ls.get("data_access_token"):
    req.add_header("Authorization", "Bearer " + ls["data_access_token"])
d = json.load(urllib.request.urlopen(req, timeout=40))
print("当前转发目标:", (d.get("forwardToOptions") or {}).get("forwardToEmail"))
for e in (d.get("forwardToOptions") or {}).get("availableEmails") or []:
    print("  可选:", e.get("type"), e.get("address"))
PY
```

改到主号（`PUT` + `forwardToEmail`，实测 200）：

```bash
curl -sS -X PUT https://appleid.apple.com/account/manage/forwardemail \
  -H "Content-Type: application/json" \
  -H "X-Apple-Api-Key: <api_key>" -H "scnt: <scnt>" \
  -H "X-Apple-ID-Session-Id: <session_id>" -H "Cookie: <cookies>" \
  -d '{"forwardToEmail":"<主号>"}'
```

sidecar 已在**每次创建别名后自动校正一次**（`ensureAppleAccountForwardTarget`），
失败只打日志不影响创建。老别名不会自动改，需要时手动跑上面的 PUT，或重新创建。

### 2. 账号同步的定时任务

注册引擎注册出的账号需要同步进 chatgpt2api 账号池，由 crontab 每分钟执行。
脚本路径必须指向真实文件：

```bash
cat /opt/sync_register_to_c2a.sh     # 必须 exec python3 /opt/chatgpt2api/sync_register_to_c2a.py
tail -5 /var/log/register_c2a_sync.log   # 若刷 "No such file or directory" 说明路径写错了
```

手动同步一次并确认数量：

```bash
/opt/sync_register_to_c2a.sh          # 输出 synced N new account(s)
```

### 3. 注册流程调用 iCloud 实时创建

注册引擎的 iCloud provider 在邮箱池为空时会自动调用 sidecar 的实时创建
（`POST /api/icloud/mailboxes/create`，走 Apple Account 新接口）补一个再领取，
并把 sidecar 返回的取码地址换成本容器可达的 sidecar 地址。
无需预先囤邮箱，注册时按需创建。

> 新接口每账号每小时约 20 个（旧接口约 5 个），触顶后 Apple 返回限流，
> sidecar 会进入冷却。批量注册时留出间隔。

---

## 别名邮箱的取码地址（给别的项目调用）

每个隐私邮箱都有一条取码地址，形如：

```
http://127.0.0.1:8788/api/v1/mailboxes/<别名邮箱>/code?key=<该邮箱的API Key>
```

带 `keyword` 与 `wait_ms` 参数，返回 JSON：成功是 `{"success":true,"code":"123456",...}`，
没收到信是 `{"success":false,"code":"no_code"}`。**这条链路实测可用**：发一封含
验证码的邮件到别名，该地址能原样取回验证码。

**但这个地址依赖 sidecar 端口被发布**。sidecar 的 API 在容器内是 8787，
`IPM_PUBLIC_BASE_URL` 指向宿主 8788；如果 8788 没被映射出来，地址是死的
（连接被拒）。发布配置在 `deploy.local.yml`：

```yaml
  icloud-privacy-mail:
    ports: !override
      - "127.0.0.1:8788:8787"
```

改动后重建：`docker compose -f docker-compose.yml -f deploy.local.yml --profile local-icloud up -d icloud-privacy-mail`

可达范围：

| 调用方 | 可用地址 | 现状 |
|---|---|---|
| 宿主进程 / nginx | `http://127.0.0.1:8788/...` | 可用 |
| 同一 docker 网络的容器（如 register-engine） | `http://icloud-privacy-mail:8787/...` | 可用 |
| 其他 docker 网络的容器 | 需把端口绑到对应网桥网关 | 未开放 |
| 公网 / 其他服务器 | 需经 nginx 反代并加访问控制 | 未开放 |

> 绑的是 `127.0.0.1`，所以公网不可达（已验证），不会把带 Key 的地址暴露出去。
> 若要给远程项目用，建议走 nginx 加一层鉴权，别直接把 8788 绑到 0.0.0.0。
