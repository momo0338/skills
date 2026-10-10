#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPA 页面正文抓取（ego-browser 兜底）——curl 412/SPA 空壳时用的一条命令。

用法:
  python3 ego_fetch_text.py <URL> <输出.txt> [--wait 12] [--space 前缀]

原理: launchctl asuser 501 + 绝对路径 ego-browser nodejs（WorkBuddy 沙箱铁律，
      见 skill ego-browser-workbuddy）；js() 取 body.innerText 落盘；
      finally completeTaskSpace(keep:false)；超时路径由 Python 侧补 sweep。
注意: 本脚本须在**完整权限**（dangerouslyDisableSandbox）下运行，否则 mach 服务连不上。
产出: 输出.txt（页面渲染文本）＋ stdout 打印 <title> 与字节数。
"""
import argparse, subprocess, sys, time, os

EGO = '/Users/zhugx/.local/bin/ego-browser'
UID = '501'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('url')
    ap.add_argument('out')
    ap.add_argument('--wait', type=int, default=12, help='SPA 渲染等待秒数')
    ap.add_argument('--space', default=None, help='task space 名（默认按时间戳唯一）')
    a = ap.parse_args()
    space = a.space or f'ego_fetch_{int(time.time())}'
    js = f'''
const SPACE = {space!r};
let err = null, meta = null;
try {{
  await useOrCreateTaskSpace(SPACE);
  await openOrReuseTab({a.url!r}, {{ wait: true, timeout: 40 }});
  await new Promise(r => setTimeout(r, {a.wait * 1000}));
  const txt = await js(String.raw`(() => document.body.innerText)()`);
  const title = await js(String.raw`(() => document.title)()`);
  const fs = await import('node:fs');
  fs.writeFileSync({a.out!r}, txt);
  meta = {{ title, len: txt.length }};
}} catch (e) {{ err = String(e); }}
finally {{ try {{ await completeTaskSpace(SPACE, {{ keep: false }}); }} catch (e) {{}} }}
if (meta) cliLog('__META__' + JSON.stringify(meta));
if (err) cliLog('__ERR__' + err);
'''
    p = subprocess.Popen(['launchctl', 'asuser', UID, EGO, 'nodejs'],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True)
    try:
        out, _ = p.communicate(js, timeout=a.wait + 90)
    except subprocess.TimeoutExpired:
        p.kill(); p.wait()
        # 超时路径 JS 的 finally 没跑，补一次 sweep
        sweep = f"await useOrCreateTaskSpace({space!r});\ntry{{await completeTaskSpace({space!r},{{keep:false}})}}catch(e){{}}"
        subprocess.run(['launchctl', 'asuser', UID, EGO, 'nodejs'], input=sweep,
                       text=True, capture_output=True, timeout=30)
        sys.exit('⛔ 超时，已补 sweep；可加大 --wait 重试')
    tail = out[-1500:]
    print(tail)
    if '__ERR__' in out:
        sys.exit(2)
    if not os.path.exists(a.out):
        sys.exit('⛔ 未产出文件（页面可能空壳：202/412 抖动属 WAF，可重试）')
    print(f'✅ 已写出 {a.out}')

if __name__ == '__main__':
    main()
