#!/usr/bin/env python3
"""
微信公众号 API 工具 (mptext.top)
通过 RESTful API 搜索公众号、获取文章列表、下载文章内容等
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

import requests


BASE_URL = "https://down.mptext.top"


def get_api_key(args_api_key: Optional[str] = None) -> str:
    """获取 API 密钥，优先级：命令行参数 > 环境变量"""
    if args_api_key:
        return args_api_key
    api_key = os.environ.get("MPTEXT_API_KEY")
    if not api_key:
        print("错误：未提供 API 密钥")
        print("请使用 --api-key 参数或设置环境变量 MPTEXT_API_KEY")
        sys.exit(1)
    return api_key


def make_request(endpoint: str, params: dict, api_key: str) -> dict:
    """发送 API 请求"""
    url = f"{BASE_URL}{endpoint}"
    headers = {"X-Auth-Key": api_key}
    
    # 配置代理
    proxies = {}
    proxy_url = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
    if proxy_url:
        proxies["http"] = proxy_url
        proxies["https"] = proxy_url
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30, proxies=proxies if proxies else None)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"请求失败：{e}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"响应解析失败：{response.text}")
        sys.exit(1)


def search_account(keyword: str, api_key: str, output: Optional[str] = None, quiet: bool = False):
    """搜索公众号"""
    if not quiet:
        print(f"搜索公众号：{keyword}")
    result = make_request("/api/public/v1/account", {"keyword": keyword}, api_key)
    
    if output:
        output_text = json.dumps(result, ensure_ascii=False, indent=2)
        Path(output).write_text(output_text, encoding="utf-8")
        if not quiet:
            print(f"结果已保存到：{output}")
    
    return result


def list_articles(fakeid: str, begin: int = 0, size: int = 20, keyword: Optional[str] = None, 
                  api_key: Optional[str] = None, output: Optional[str] = None, quiet: bool = False):
    """获取文章列表"""
    params = {"fakeid": fakeid, "begin": begin, "size": size}
    if keyword:
        params["keyword"] = keyword
    
    if not quiet:
        print(f"获取文章列表：fakeid={fakeid}")
        if keyword:
            print(f"关键词：{keyword}")
    
    result = make_request("/api/public/v1/article", params, api_key)
    
    if output:
        output_text = json.dumps(result, ensure_ascii=False, indent=2)
        Path(output).write_text(output_text, encoding="utf-8")
        if not quiet:
            print(f"结果已保存到：{output}")
    
    return result


def download_article(url: str, format: str = "html", api_key: Optional[str] = None, 
                     output: Optional[str] = None):
    """下载文章内容"""
    print(f"下载文章：{url}")
    print(f"格式：{format}")
    
    result = make_request("/api/public/v1/download", {"url": url, "format": format}, api_key)
    
    if output:
        if format == "html":
            Path(output).write_text(result.get("content", ""), encoding="utf-8")
        elif format == "markdown":
            Path(output).write_text(result.get("content", ""), encoding="utf-8")
        elif format == "text":
            Path(output).write_text(result.get("content", ""), encoding="utf-8")
        elif format == "json":
            Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"文章已保存到：{output}")
    else:
        if format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(result.get("content", ""))
    
    return result


def get_account_by_url(url: str, api_key: Optional[str] = None, output: Optional[str] = None):
    """通过文章 URL 获取公众号信息"""
    print(f"通过 URL 获取公众号信息：{url}")
    result = make_request("/api/public/v1/accountbyurl", {"url": url}, api_key)
    
    output_text = json.dumps(result, ensure_ascii=False, indent=2)
    
    if output:
        Path(output).write_text(output_text, encoding="utf-8")
        print(f"结果已保存到：{output}")
    else:
        print(output_text)
    
    return result


def verify_key(api_key: str):
    """验证 API 密钥"""
    print("验证 API 密钥...")
    result = make_request("/api/public/v1/authkey", {}, api_key)
    
    if result.get("code") == 0:
        print("API 密钥有效")
    else:
        print("API 密钥已过期或无效")
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def batch_download(fakeid: str, format: str = "markdown", output_dir: str = "./articles",
                   limit: Optional[int] = None, keyword: Optional[str] = None, 
                   api_key: Optional[str] = None):
    """批量下载文章"""
    print(f"批量下载文章：fakeid={fakeid}")
    print(f"格式：{format}")
    print(f"输出目录：{output_dir}")
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    begin = 0
    size = 20
    total_downloaded = 0
    
    while True:
        articles = list_articles(fakeid, begin=begin, size=size, keyword=keyword, api_key=api_key)
        
        article_list = articles.get("list", [])
        if not article_list:
            break
        
        for article in article_list:
            if limit and total_downloaded >= limit:
                break
            
            title = article.get("title", "untitled")
            link = article.get("link", "")
            
            if not link:
                continue
            
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            ext = "html" if format == "html" else "md" if format == "markdown" else "txt" if format == "text" else "json"
            filename = f"{safe_title}.{ext}"
            filepath = os.path.join(output_dir, filename)
            
            print(f"下载：{title}")
            download_article(link, format=format, api_key=api_key, output=filepath)
            total_downloaded += 1
            
            if limit and total_downloaded >= limit:
                break
        
        if limit and total_downloaded >= limit:
            break
        
        if len(article_list) < size:
            break
        
        begin += size
    
    print(f"批量下载完成，共下载 {total_downloaded} 篇文章")


def main():
    parser = argparse.ArgumentParser(description="微信公众号 API 工具 (mptext.top)")
    parser.add_argument("--api-key", help="API 密钥")
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    search_parser = subparsers.add_parser("search-account", help="搜索公众号")
    search_parser.add_argument("keyword", help="公众号名称关键词")
    search_parser.add_argument("-o", "--output", help="输出文件路径")
    
    list_parser = subparsers.add_parser("list-articles", help="获取文章列表")
    list_parser.add_argument("fakeid", help="公众号的 fakeid")
    list_parser.add_argument("--begin", type=int, default=0, help="起始位置，默认 0")
    list_parser.add_argument("--size", type=int, default=20, help="每页数量，默认 20")
    list_parser.add_argument("--keyword", help="文章标题搜索关键词")
    list_parser.add_argument("-o", "--output", help="输出文件路径")
    
    download_parser = subparsers.add_parser("download-article", help="下载文章内容")
    download_parser.add_argument("url", help="微信文章 URL")
    download_parser.add_argument("--format", choices=["html", "markdown", "text", "json"], 
                                default="html", help="输出格式，默认 html")
    download_parser.add_argument("-o", "--output", help="输出文件路径")
    
    account_parser = subparsers.add_parser("get-account-by-url", help="通过文章 URL 获取公众号信息")
    account_parser.add_argument("url", help="微信文章 URL")
    account_parser.add_argument("-o", "--output", help="输出文件路径")
    
    verify_parser = subparsers.add_parser("verify-key", help="验证 API 密钥")
    
    batch_parser = subparsers.add_parser("batch-download", help="批量下载文章")
    batch_parser.add_argument("fakeid", help="公众号的 fakeid")
    batch_parser.add_argument("--format", choices=["html", "markdown", "text", "json"], 
                             default="markdown", help="输出格式，默认 markdown")
    batch_parser.add_argument("--output-dir", default="./articles", help="输出目录，默认 ./articles")
    batch_parser.add_argument("--limit", type=int, help="下载数量限制")
    batch_parser.add_argument("--keyword", help="文章标题搜索关键词")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    api_key = get_api_key(args.api_key)
    
    if args.command == "search-account":
        search_account(args.keyword, api_key, args.output)
    elif args.command == "list-articles":
        list_articles(args.fakeid, args.begin, args.size, args.keyword, api_key, args.output)
    elif args.command == "download-article":
        download_article(args.url, args.format, api_key, args.output)
    elif args.command == "get-account-by-url":
        get_account_by_url(args.url, api_key, args.output)
    elif args.command == "verify-key":
        verify_key(api_key)
    elif args.command == "batch-download":
        batch_download(args.fakeid, args.format, args.output_dir, args.limit, args.keyword, api_key)


if __name__ == "__main__":
    main()
