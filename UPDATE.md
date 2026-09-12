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
