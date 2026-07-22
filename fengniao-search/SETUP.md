# 风鸟企业查询 Skill 本地验证说明

## 适用范围

本文只用于本地验证当前 skill，不要求修改用户主目录、shell 启动文件或 agent 全局配置。

## 前置条件

- Node.js 18 或以上版本
- 一个可用的 `FN_API_KEY`

验证 Node.js 版本：

```bash
node -v
```

## 获取 API Key

请登录风鸟 Web 端，在「账户设置 > API Key」页面生成个人 API Key。

- 完整 Key 仅在创建成功时展示一次，请及时复制并妥善保存
- 如需安装或更新 Skill，可点击页面中的「一键配置风鸟skill」下载最新包
- 不要将完整 Key 放在截图、聊天记录或公开文档中
- 左上角“美亚风鸟” Logo 可点击跳转风鸟官网

## API 额度限制

- 多个 API Key 共用同一账号的每日额度，创建多个 Key 不会增加每日可用次数
- 当接口返回 `code=9999` 且 `msg` 包含“访问已达上限”时，表示当前账号当日额度已用完，不是本地配置错误
- 额度查看方式：访问「账户设置 > API Key」页面查看今日调用和账号剩余额度

## 临时设置 API Key

只在当前终端会话中设置，关闭终端后失效。

**macOS / Linux**

```bash
export FN_API_KEY="你的API Key"
```

**Windows PowerShell**

```powershell
$env:FN_API_KEY = "你的API Key"
```

**Windows CMD**

```cmd
set FN_API_KEY=你的API Key
```

## 校验环境变量

建议在调用查询前先确认当前会话已经能读到 `FN_API_KEY`。

**macOS / Linux**

```bash
printenv FN_API_KEY
```

**Windows PowerShell**

```powershell
$env:FN_API_KEY
```

也可以使用更显式的写法：

```powershell
Get-Item Env:FN_API_KEY -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Value
```

如果你是在另一个 PowerShell 进程里执行校验命令，优先使用单引号包裹命令，避免外层 shell 提前展开变量：

```powershell
powershell -Command '$env:FN_API_KEY'
```

不要把下面这类命令的报错直接当成“环境变量未配置”的证据：

```powershell
powershell -Command "echo $env:FN_API_KEY"
```

原因是外层 shell 可能先展开 `$env:FN_API_KEY`；当它为空时，传给内层 PowerShell 的就只剩 `echo`，从而触发 `Write-Output` 缺少 `InputObject` 的误报。

## 本地验证命令

```bash
# 1. 测试工具发现（无需联网）
node scripts/tool.mjs discover "企业基本信息"

# 2. 测试模糊搜索（需要有效 API Key）
node scripts/tool.mjs call biz_fuzzy_search --params '{"key":"腾讯"}'

# 3. 测试维度查询（用上一步返回的 entid）
node scripts/tool.mjs call biz_basic_info --params '{"entid":"AerjZTfkSh0"}'
```

## 当前发布包的安全边界

- 只从环境变量 `FN_API_KEY` 读取凭证
- 只读取 skill 包内的 `tools.json` 和 `references/` 文件
- 不读取用户主目录中的 agent 配置或 shell 启动配置
- 不写入本地文件
- API 凭证读取自环境变量，但实际调用时通过 URL 参数 `apikey` 发送，不通过 HTTP 请求头发送

## 环境说明

当前下载包默认使用生产环境地址 `https://m.riskbird.com/prod-qbb-api`。

如需内部联调临时切换地址，可设置环境变量 `FN_API_BASE_URL`。普通用户无需配置该变量。
