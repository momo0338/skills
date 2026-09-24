---
name: net-reachability-diagnosis
description: 诊断"某台主机/某个端口连不上"的分层排查流程。核心价值：识破 macOS 上 TUN 代理（Clash Verge Rev / Mihomo）造成的选择性阻断与端口探测伪造，读 Clash 配置定位规则命中点，用同通道对照实验锁定"目标问题 vs 通道问题"，并以源 IP 双证据验证修复。触发词：连不上、SSH 不通、端口不通、ping 通但 SSH 不通、HTTP 通 SSH 不通、代理导致连不上、TUN 劫持、utun0、198.18、Clash 规则、DIRECT 规则、假连接、kex_exchange_identification。
---

# 网络可达性诊断（TUN 代理环境）

## 何时用

- "XX 主机连不上了"、"ping 通但 SSH 不通"、"某端口不通"
- **选择性阻断**：HTTP/HTTPS 能通，但 SSH / 数据库 / 其他非 HTTP 协议不通
- 换了网络环境后某服务突然不可达

## 四条铁律（先记住，能省几小时）

1. **分层验证，不许跳层** —— ICMP → TCP 握手 → 应用协议（banner/kex），先定位断在哪一层。
2. **绝不用 `nc -z` 判断端口** —— TUN/透明代理会让**所有**端口都报 OPEN，结论全废。
3. **路由表能看出 TUN 劫持，但不能用来判断规则是否生效** —— TUN 开着时路由永远不变。
4. **同通道对照实验**是区分"目标主机问题"和"代理通道问题"的杀器。

## Step 1 · 分层探测

```bash
ping -c 3 <IP>                                                     # L3 通不通
nc -z -G 3 -w 3 <IP> <port>                                        # L4（⚠️ 结果可能被伪造）
curl -sS -m 10 -o /dev/null -w "%{http_code}\n" http://<IP>:<port>/ # L7 HTTP
ssh -vvv -o ConnectTimeout=10 -o BatchMode=yes <host> 'true'       # L7 SSH 握手细节
```

判读速查：

| 现象 | 含义 |
|---|---|
| `Connection established` + `Local version string` 后**无 banner** | 传输层被中间设备掐断（代理/防火墙） |
| `kex_exchange_identification: Connection closed by remote host` | 对端或中间设备在 SSH banner 前主动 close |
| `Connection timed out` | 更可能是丢包 / 防火墙 DROP |
| 有效 HTTP 状态码（401/200 等）+ 真实 Server 头 | HTTP 链路真的通 |

## Step 2 · 识破端口探测伪造（必做）

挑几个**目标机上必然关闭**的端口做对照：

```bash
for p in 22 12345 54321 9999 65000; do
  nc -z -G 3 -w 3 <IP> $p >/dev/null 2>&1 && echo "$p OPEN" || echo "$p CLOSED"
done
```

**若必然关闭的端口也报 OPEN ⇒ 端口探测被代理整体伪造，此前所有扫描结论作废。**

进一步坐实代理在中间：

```bash
curl -sS -m 8 -i http://<IP>:22/     # 真实 sshd 绝不会回 HTTP；有状态码 = 代理在应答
```

## Step 3 · 判断是否 TUN 代理劫持

```bash
route -n get <IP>                          # 看 gateway / interface
netstat -rn -f inet | head -25             # 看是否出现 1 / 2/7 / 4/6 / 8/5 / 16/4 / 32/3 / 64/2 / 128.0/1
ifconfig utun0 2>/dev/null | head -5
```

判据：

- `gateway: 198.18.0.1` + `interface: utun0` ⇒ 流量进了 TUN。
- 路由表中 `1`、`2/7`、`4/6`、`8/5`、`16/4`、`32/3`、`64/2`、`128.0/1` **全部指向同一 utun** ⇒ TUN 把整个 IPv4 拆段全量劫持。
- `ifconfig utun0` 出现 `inet6 fdfe:dcba:9876::1/126` ⇒ **Mihomo / Clash.Meta** 特征（`9876` 是 Clash 默认混合端口号）。
- `198.18.0.0/15` 属 RFC 2544 benchmark 段，是 fake-IP 代理的常见网关。

定位代理本体（macOS 常见位置）：

```bash
ls -d ~/Library/Application\ Support/io.github.clash-verge-rev.clash-verge-rev   # Clash Verge Rev
ls -d ~/.config/mihomo ~/.config/clash ~/Library/Application\ Support/ClashX* 2>/dev/null
```

## Step 4 · 读配置，定位规则命中点

```bash
D=~/Library/Application\ Support/io.github.clash-verge-rev.clash-verge-rev
# 端口与控制器
grep -nE "^(mixed-port|port|socks-port|redir-port|mode|external-controller):" "$D/config.yaml"
# rules 尾部（决定兜底走向）
awk '/^rules:/{f=1;next} f&&/^[a-z-]+:/{f=0} f' "$D/clash-verge.yaml" | tail -15
# 是否有端口/进程类规则
awk '/^rules:/{f=1;next} f&&/^[a-z-]+:/{f=0} f' "$D/clash-verge.yaml" | grep -cE "DST-PORT|PROCESS-NAME|PROCESS-PATH"
```

判读要点：

- 规则自上而下**首条命中即止**。
- 境外 IP **不会**命中 `GEOIP,CN,DIRECT`（如东京 `43.167.*`、AS132203 等）⇒ 直落兜底 `MATCH,<节点选择组>` ⇒ **被送去远程代理节点**。
- **机场节点普遍封禁 22 / 25 端口** ⇒ 这就是"HTTP 全通、SSH 单独不通"的典型成因。
- 若全表**没有** `DST-PORT` / `PROCESS-NAME` 规则，说明阻断不来自分流，而是节点端口策略。

## Step 5 · 同通道对照实验（区分目标 vs 通道）

拿代理自己的 mixed-port 做对照：

```bash
P=<mixed-port>   # 从 config.yaml 读，如 7897
curl -sS -m 8 -x http://127.0.0.1:$P -o /dev/null -w "已知可达端口=%{http_code}\n" http://<IP>:<port_ok>/
curl -sS -m 8 -x http://127.0.0.1:$P -p -o /dev/null -w "问题端口=%{http_code}\n" telnet://<IP>:<port_bad>
```

**同一通道、同一 IP，A 端口 200 而 B 端口 000 ⇒ 问题在通道（节点）对端口的策略，与目标主机无关。**

## Step 6 · 修复

在 Clash Verge 的**扩展配置 / Merge** 中写（**持久，订阅更新不覆盖**）：

```yaml
prepend-rules:
  - IP-CIDR,<目标IP>/32,DIRECT,no-resolve
```

- 次选：在订阅 profile 的 `rules` 段**最前面**加同一行 —— **会被订阅更新冲掉，仅作临时**。
- 最快验证：Clash Verge 切「直连模式」，若立刻恢复即坐实判断。

## Step 7 · 验证（双证据）

```bash
ssh <host> 'echo $SSH_CLIENT; hostname; uptime'
```

- `$SSH_CLIENT` 的源 IP = **本地家宽 IP** ⇒ DIRECT 已生效。
- 源 IP = **代理节点 IP** ⇒ 仍走代理，规则未命中。

⚠️ **不要用路由表判断规则是否生效**：TUN 仍开启时路由表不会变化，只是命中 DIRECT 的流被内核"漏"出去直连。

## 反面清单（真实踩坑，勿重犯）

| ❌ 错误做法 | 后果 / 正解 |
|---|---|
| 用 `nc -z` 判断端口是否开放 | 被代理伪造，全部报 OPEN → 改用同通道对照 + 真实协议探测 |
| 归因"沙箱/权限限制" | 本次真因是 TUN 代理，沙箱无辜 |
| 归因"必须回真实终端" | TUN 是**系统级**路由，iTerm 同样被劫持 |
| 用路由表判断 Clash 规则是否生效 | 路由不变 ≠ 规则没生效，看 `$SSH_CLIENT` |
| 直接把规则写进 `clash-verge.yaml` | 订阅更新会冲掉 → 用扩展配置 `prepend-rules` |

## 附：快速判定表

| ICMP | HTTP | SSH | 最可能结论 |
|---|---|---|---|
| 通 | 通 | 不通 | **代理节点封 22**（本流程主战场） |
| 通 | 通 | 通 | 正常 |
| 通 | 不通 | 不通 | 代理节点故障 / 规则 REJECT 全量 |
| 不通 | 不通 | 不通 | 主机宕机、安全组、或本机路由异常 |
