# dy-cli 0.2.2 登录误报修复补丁（本机）

> 2026-08-12 本机补丁。**`pip install -U dy-cli` 升级会覆盖以下修改，需重新应用。**
> 适用前提：`dy status` 显示"已登录"但 `dy search` 报"请先登录，再继续搜索吧"。

## 根因

1. `dy login --browser` 的登录判定把游客字段当登录凭证：
   - `dy_cli/commands/auth.py` 原 `key_names = {"sessionid", "passport_csrf_token", "odin_tt", "sid_guard"}`
   - `odin_tt` / `passport_csrf_token` / `ttwid` 是访客态字段，浏览器未登录也能提取到 → 误报"登录成功"
2. `dy status` 的 `check_login` 靠 Playwright 打开创作者平台猜页面元素：
   - 8 秒窗口内没检测到登录页跳转/文案就误判"已登录"

## 修复内容

### 1. commands/auth.py — key_names 收窄为真实会话字段

```python
key_names = {"sessionid", "sessionid_ss", "sid_tt", "sid_guard", "uid_tt", "passport_auth_status"}
```

### 2. engines/playwright_client.py — check_login 改为静态 + 服务端双校验

- 新增 `_has_real_session()`：静态检查 Cookie 文件是否含真实会话字段（游客字段不算），无则直接返回未登录（即时，不启动浏览器）
- 新增 `_check_login_server()`：请求 `https://www.douyin.com/aweme/v1/web/user/profile/self/`
  - `status_code == 0` 且含 `user` → 已登录
  - `status_code == 8` "用户未登录" → 未登录
- `_check_login_async()`：服务端校验优先；网络异常时回退到原 Playwright 页面检测

## 验证（补丁后行为）

| 场景 | 修复前 | 修复后 |
|---|---|---|
| 浏览器未登录 + `dy login --browser` | 误报"登录成功" | "提取了 34 个 cookie，但缺少登录态" + False |
| 浏览器未登录 + `dy status` | 误报"已登录" | "Cookie 已失效"（即时返回） |
| 真登录后 + `dy search` | — | 服务端校验通过，搜索恢复 |

## 恢复登录的正确路径

1. 浏览器（Chrome）打开 douyin.com，扫码/手机号登录，确认出现个人主页
2. `dy login --browser` → 这次应提示"提取了 N 个 cookie (含登录态)"
3. `dy status` → "已登录"；`dy search "xxx"` → 正常返回
