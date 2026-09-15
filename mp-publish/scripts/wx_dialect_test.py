#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""微信正文方言批量实证测试器
用法: python wx_dialect_test.py <测试名> <含{CONTENT}的样本模板文件或直接传html>
推送一条草稿 -> draft/get 读回 -> 输出读回HTML -> 删除测试草稿
"""
import json, os, subprocess, sys, re

def _read_cred_file(p):
    try:
        with open(p, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""

def load_wx_creds():
    """从环境变量或 ~/.config/weixin/ 文件读取 AppID/AppSecret，绝不硬编码到仓库。"""
    appid = os.environ.get("WX_APPID") or _read_cred_file(os.path.expanduser("~/.config/weixin/appid"))
    secret = os.environ.get("WX_APPSECRET") or _read_cred_file(os.path.expanduser("~/.config/weixin/appsecret"))
    if not appid or not secret:
        sys.stderr.write("⚠️ 未配置微信凭据：请设置环境变量 WX_APPID/WX_APPSECRET，"
                         "或在 ~/.config/weixin/ 下放置 appid / appsecret 文件\n")
        sys.exit(2)
    return appid, secret

APPID, SECRET = load_wx_creds()

def curl(url, data=None, extra=None):
    e = (["--data-binary", json.dumps(data, ensure_ascii=False),
          "-H", "Content-Type: application/json; charset=utf-8"]
         if data is not None else (extra or []))
    r = subprocess.run(["curl", "-s", "--max-time", "60", url] + e,
                       capture_output=True, text=True)
    return json.loads(r.stdout)

def main():
    name = sys.argv[1]
    content = open(sys.argv[2], encoding="utf-8").read()
    tok = curl(f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APPID}&secret={SECRET}")
    T = tok["access_token"]
    payload = {"articles": [{"title": f"方言测试-{name}-请忽略",
                             "author": "满爸爱生活", "digest": "测试",
                             "content": content,
                             "thumb_media_id": "m9YR9nbv61wLzRbCzknE-GZK7ZPuAWPv3yWFrf8RM0gEbuzg4N_RaCwyPVLf703J",
                             "need_open_comment": 0, "only_fans_can_comment": 0}]}
    r = curl(f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={T}", payload)
    mid = r.get("media_id")
    if not mid:
        print("draft/add 失败:", r); sys.exit(1)
    g = curl(f"https://api.weixin.qq.com/cgi-bin/draft/get?access_token={T}", {"media_id": mid})
    back = g.get("news_item", [{}])[0].get("content", "")
    print(f"===== {name} 读回 ({len(back)} 字符) =====")
    print(back)
    curl(f"https://api.weixin.qq.com/cgi-bin/draft/delete?access_token={T}", {"media_id": mid})
    print("\n===== 测试草稿已删除 =====")

if __name__ == "__main__":
    main()
