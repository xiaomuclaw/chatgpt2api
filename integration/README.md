# integration/ — 本项目相对上游 chatgpt2api 的增补

本目录让「iCloud 邮箱 + 注册引擎页面」这两块增补可以**在上游升级后一键重新贴上**，
不必手工合并。

## 组成

| 路径 | 作用 |
|---|---|
| `assets/` | 增补用到的全部文件快照（注册页、iCloud 页、sidecar 源码等） |
| `attach.py` | 一键重新贴回增补（幂等，可反复运行） |

## 上游升级后如何操作

```bash
cd /opt/chatgpt2api
git fetch upstream
git merge upstream/main            # 冲突时保留上游版本（我们的改动由 attach.py 补回）
python3 integration/attach.py      # 重新贴回 iCloud + 注册页
docker compose -f docker-compose.yml -f deploy.local.yml --profile local-icloud up -d --build
```

## attach.py 会做什么

1. 从 `assets/` 恢复全部增补文件（~44 个，纯新增，本不与上游冲突）
2. 对上游的 5 个文件做**最小补丁**（幂等，已打过就跳过）：
   - `api/app.py` — 注册 iCloud 路由（2 行）
   - `web-vue/src/router/routes.ts` — 加 `/register`、`/icloud` 路由
   - `web-vue/src/layouts/AppShell.vue` — 加两个侧边栏入口 + 标题 + 预加载
   - `docker-compose.yml` — 加 iCloud sidecar 服务 + 环境变量
3. 重新生成 lucide 图标集（新页面引用的图标需要登记，否则构建会报
   `Local Lucide icon set is stale`）

若某文件上游改动过大、锚点找不到，脚本会**明确指出该文件需手工合并**并以非 0 退出。

## 注册引擎（另一个仓库，独立升级）

注册后端在 **另一个仓库** `gptGrok2api-py`，本目录不涉及。它单独升级：

```bash
cd /opt/chatgpt2api/register-engine
git pull origin main
docker compose -f docker-compose.yml -f deploy.local.yml up -d --build
docker compose -f deploy/docker-compose.captcha-solver.yml -f deploy.captcha.yml up -d --build
```

本增补只需保证 nginx 把 `/api/register*` 与 `/register/` 指向注册引擎（见仓库 `DEPLOY.md` 第五节）。

## 注册引擎前端更新后如何同步内嵌页

注册**逻辑**在后端，后端更新无需同步前端。只有当注册引擎的**前端页面**变了
（新增字段/按钮），又希望 chatgpt2api 里内嵌的页面跟着变时：

```bash
# 参数为注册引擎目录（默认 ./register-engine）
bash integration/sync-from-engine.sh
python3 integration/attach.py
docker compose -f docker-compose.yml -f deploy.local.yml --profile local-icloud up -d --build
```

`sync-from-engine.sh` 会做两件事：
1. 从注册引擎复制 16 个注册页前端文件到 `integration/assets/`
2. 把其中的 `@/api/proxy` 改写成 `@/api/proxyRegister`

> 第 2 步很关键：chatgpt2api 自己的 `api/proxy.ts` 用的是另一套代理引用模型
> （`{mode,group_id,url}`），所以内嵌页必须改用本仓库提供的兼容模块
> `api/proxyRegister.ts`。不改写会构建失败。

## 目录内容

| 路径 | 说明 |
|---|---|
| `integration/assets/` | 增补文件快照（43 个） |
| `integration/attach.py` | 一键贴回增补（幂等） |
| `integration/sync-from-engine.sh` | 从注册引擎刷新前端快照 |

## nginx 路由约定（重要）

站点下**只暴露一个控制台**（chatgpt2api 自身，含内嵌注册页）：

```
/                 -> chatgpt2api 控制台（含侧边栏「注册账号」-> #/register）
/#/register       -> 内嵌注册页（调 /api/register*）
/api/register*    -> 注册引擎后端 (127.0.0.1:8012)
/register/        -> 重定向回内嵌页（不再暴露注册引擎自带控制台）
```

**为什么不暴露注册引擎自带控制台**：它是 GPTGrok2API 那套界面（品牌与版本号都不同，
显示为 GPTGrok2API v1.2.1），挂在 chatgpt2api 域名下会造成混淆。其功能已全部内嵌，
因此统一重定向。

nginx 参考配置：

```nginx
# 内嵌注册页的后端接口
location ^~ /api/register {
    proxy_pass http://127.0.0.1:8012;
    include /etc/nginx/snippets/proxy-common.conf;
}
# 旧入口重定向到内嵌页（nginx 中 # 是注释，故用 HTML/JS 跳转）
location = /register { return 302 /; }
location ^~ /register/ {
    default_type text/html;
    return 200 '<!doctype html><meta charset="utf-8"><title>Redirecting</title><script>location.replace("/" + String.fromCharCode(35) + "/register")</script><noscript><a href="/">enter console</a></noscript>';
}
location / {
    proxy_pass http://127.0.0.1:3000;
    include /etc/nginx/snippets/proxy-common.conf;
}
```
