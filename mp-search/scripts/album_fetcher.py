#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
微信公众号合集（Album）获取服务
负责获取合集的全部文章列表，生成Markdown索引文件

参考实现：https://github.com/SlowGrowth1314/opencli-weixin-album
"""

import json
import os
import random
import re
import sys
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import requests

from utils import cache_manager


# ============================================================
# 类型定义
# ============================================================

class AlbumArticle:
    """合集文章"""
    def __init__(self, title: str, url: str, create_time: str, msgid: str, itemidx: str):
        self.title = title
        self.url = url
        self.create_time = create_time
        self.msgid = msgid
        self.itemidx = itemidx
    
    def to_dict(self) -> Dict:
        return {
            'title': self.title,
            'url': self.url,
            'create_time': self.create_time,
            'msgid': self.msgid,
            'itemidx': self.itemidx,
        }


# ============================================================
# URL解析
# ============================================================

def parse_album_url(raw_url: str) -> Optional[Dict[str, str]]:
    """解析微信合集URL，提取biz、album_id等参数"""
    url = raw_url.strip()
    
    # 去除引号
    if (url.startswith('"') and url.endswith('"')) or (url.startswith("'") and url.endswith("'")):
        url = url[1:-1].strip()
    
    # 补全协议
    if url.startswith('mp.weixin.qq.com/') or url.startswith('//mp.weixin.qq.com/'):
        url = 'https://' + url.lstrip('/')
    
    try:
        parsed = urlparse(url)
        if parsed.hostname != 'mp.weixin.qq.com':
            return None
        
        params = parse_qs(parsed.query)
        biz = params.get('__biz', [None])[0]
        album_id = params.get('album_id', [None])[0]
        scene = params.get('scene', ['126'])[0]
        
        if not biz or not album_id:
            return None
        
        return {'biz': biz, 'album_id': album_id, 'scene': scene}
    except Exception as e:
        print(f"解析URL失败: {e}", file=sys.stderr)
        return None


# ============================================================
# API调用
# ============================================================

API_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'X-Requested-With': 'XMLHttpRequest',
    'Referer': 'https://mp.weixin.qq.com/',
}


def fetch_album_page(
    biz: str,
    album_id: str,
    count: int = 20,
    cursor: Optional[Dict[str, str]] = None
) -> Dict:
    """获取合集单页文章列表"""
    api_url = (
        f"https://mp.weixin.qq.com/mp/appmsgalbum"
        f"?action=getalbum"
        f"&__biz={biz}"
        f"&album_id={album_id}"
        f"&count={count}"
        f"&f=json"
    )
    
    if cursor:
        api_url += f"&begin_msgid={cursor['msgid']}&begin_itemidx={cursor['itemidx']}"
    
    # 检查缓存
    cache_key = f"album_page:{api_url}"
    cached = cache_manager.get(cache_key)
    if cached:
        return cached
    
    try:
        response = requests.get(api_url, headers=API_HEADERS, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('base_resp', {}).get('ret') != 0:
            raise Exception(f"API错误: {data.get('base_resp', {}).get('ret')}")
        
        # 缓存结果
        cache_manager.set(cache_key, data)
        
        return data
    except requests.exceptions.RequestException as e:
        raise Exception(f"API请求失败: {e}")


def fetch_all_articles(
    biz: str,
    album_id: str,
    batch_size: int = 20
) -> Tuple[List[AlbumArticle], str]:
    """获取合集全部文章列表（自动翻页）"""
    all_articles = []
    album_title = album_id
    cursor = None
    
    print(f"\n📦 正在获取合集: {album_id}", file=sys.stderr)
    
    while True:
        # 获取单页
        data = fetch_album_page(biz, album_id, batch_size, cursor)
        
        # 解析响应
        getalbum_resp = data.get('getalbum_resp', {})
        article_list = getalbum_resp.get('article_list', [])
        base_info = getalbum_resp.get('base_info', {})
        continue_flag = getalbum_resp.get('continue_flag') == '1'
        
        # 提取专辑名称
        if base_info.get('title'):
            album_title = base_info['title']
            if len(all_articles) == 0:
                print(f"📖 合集名称: {album_title}", file=sys.stderr)
        
        # 解析文章列表
        if not article_list or len(article_list) == 0:
            break
        
        for article in article_list:
            msg_info = article.get('msg_info', {})
            title = msg_info.get('title', '')
            url = msg_info.get('url', '')
            create_time = str(msg_info.get('create_time', ''))
            msgid = str(msg_info.get('msgid', ''))
            itemidx = str(msg_info.get('itemidx', ''))
            
            # 修复URL协议
            if url.startswith('http://'):
                url = url.replace('http://', 'https://')
            
            if title and url:
                all_articles.append(AlbumArticle(title, url, create_time, msgid, itemidx))
        
        print(f"📥 已获取 {len(all_articles)} 篇", file=sys.stderr)
        
        # 检查是否需要继续翻页
        if not continue_flag:
            break
        
        # 更新游标
        if article_list:
            last_article = article_list[-1]
            msg_info = last_article.get('msg_info', {})
            cursor = {
                'msgid': str(msg_info.get('msgid', '')),
                'itemidx': str(msg_info.get('itemidx', '')),
            }
        
        # 随机延迟，避免触发限流
        pause = 1 + random.uniform(0, 2)
        time.sleep(pause)
    
    print(f"✅ 共收集 {len(all_articles)} 篇文章链接", file=sys.stderr)
    
    return all_articles, album_title


# ============================================================
# Markdown索引生成
# ============================================================

def sanitize_filename(name: str) -> str:
    """清理文件名，移除非法字符"""
    return re.sub(r'[\/\\:*?"<>|]', '_', name).strip()


def generate_markdown_index(
    articles: List[AlbumArticle],
    album_title: str,
    output_dir: str
) -> str:
    """生成Markdown索引文件"""
    safe_name = sanitize_filename(album_title)
    album_dir = os.path.join(output_dir, safe_name)
    os.makedirs(album_dir, exist_ok=True)
    
    index_path = os.path.join(album_dir, f"{safe_name}.md")
    
    # 检查是否已有索引（增量下载支持）
    existing_entries = {}
    if os.path.exists(index_path):
        existing_entries = parse_index_md(index_path)
        print(f"📋 发现已有索引: {len(existing_entries)} 篇已下载", file=sys.stderr)
    
    # 生成Markdown内容
    header = "| # | 标题 | URL | 本地路径 | 发布时间 |"
    separator = "|---|------|-----|---------|---------|"
    
    rows = []
    for i, article in enumerate(articles, 1):
        # 检查是否已有本地路径
        local_path = existing_entries.get(i, '')
        
        # 格式化时间
        if article.create_time and article.create_time.isdigit():
            timestamp = int(article.create_time)
            from datetime import datetime
            time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
        else:
            time_str = '-'
        
        rows.append(f"| {i} | {article.title} | {article.url} | {local_path} | {time_str} |")
    
    content = '\n'.join([header, separator] + rows) + '\n'
    
    # 写入文件
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"📄 索引文件: {index_path}", file=sys.stderr)
    
    return index_path


def parse_index_md(index_path: str) -> Dict[int, str]:
    """解析Markdown索引文件，提取已下载的文章"""
    if not os.path.exists(index_path):
        return {}
    
    entries = {}
    with open(index_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.startswith('|') or '---' in line:
                continue
            
            cols = [c.strip() for c in line.split('|')]
            if len(cols) >= 6 and cols[1].isdigit():
                index = int(cols[1])
                local_path = cols[4] if cols[4] else ''
                if local_path:
                    entries[index] = local_path
    
    return entries


def update_md_local_path(index_path: str, index: int, local_path: str):
    """更新Markdown索引文件中的本地路径"""
    if not os.path.exists(index_path):
        return
    
    with open(index_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        if line.startswith(f"| {index} |") or line.startswith(f"| {index}  |"):
            cols = line.split('|')
            if len(cols) >= 6:
                cols[4] = f" {local_path} "
                lines[i] = '|'.join(cols)
                break
    
    with open(index_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)


# ============================================================
# 主函数
# ============================================================

def fetch_album(
    url: str,
    output_dir: str = './weixin-albums',
    batch_size: int = 20,
    download_articles: bool = False
) -> Dict:
    """
    获取微信公众号合集文章列表
    
    参数:
        url: 微信合集页面URL或已有索引文件路径
        output_dir: 输出目录
        batch_size: 每页获取文章数（最大20）
        download_articles: 是否下载文章（需要opencli）
    
    返回:
        包含文章列表和索引路径的字典
    """
    # 检查是否为增量下载模式
    local_index_path = None
    existing_entries = {}
    
    if url.endswith('.md') and os.path.exists(url):
        local_index_path = os.path.abspath(url)
        existing_entries = parse_index_md(local_index_path)
        print(f"\n📋 增量更新模式: {local_index_path}", file=sys.stderr)
        print(f"   已有索引: {len(existing_entries)} 篇", file=sys.stderr)
        
        # 从索引文件所在目录输出
        output_dir = os.path.dirname(local_index_path)
    
    # 解析URL
    parsed = parse_album_url(url)
    if not parsed:
        raise ValueError(f"无效的合集URL: {url}")
    
    biz = parsed['biz']
    album_id = parsed['album_id']
    batch_size = min(batch_size, 20)  # 微信API限制
    
    # 获取全部文章
    articles, album_title = fetch_all_articles(biz, album_id, batch_size)
    
    if not articles:
        raise Exception("未获取到任何文章")
    
    # 生成Markdown索引（支持增量更新）
    index_path = generate_markdown_index(articles, album_title, output_dir)
    
    # 统计新增文章
    new_count = 0
    for i, article in enumerate(articles, 1):
        if i not in existing_entries:
            new_count += 1
    
    result = {
        'album_title': album_title,
        'total_articles': len(articles),
        'new_articles': new_count,
        'articles': [a.to_dict() for a in articles],
        'index_path': index_path,
        'status': 'success',
    }


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='获取微信公众号合集文章列表')
    parser.add_argument('url', help='微信合集页面URL')
    parser.add_argument('-o', '--output', default='./weixin-albums', help='输出目录')
    parser.add_argument('-b', '--batch-size', type=int, default=20, help='每页获取文章数（最大20）')
    
    args = parser.parse_args()
    
    result = fetch_album(args.url, args.output, args.batch_size)
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
