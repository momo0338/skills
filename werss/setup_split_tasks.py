import urllib.request
import json
import sys

CONFIG_FILE = '/Users/zhugx/src/skills/werss/config.json'
with open(CONFIG_FILE, 'r') as f:
    cfg = json.load(f)

BASE_URL = cfg['base_url'].rstrip('/')
AK = cfg['access_key']
SK = cfg['secret_key']
AUTH_HEADER = {
    'Authorization': f'AK-SK {AK}:{SK}',
    'Content-Type': 'application/json'
}

def api_call(path, method='GET', data=None):
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode('utf-8') if data is not None else None
    req = urllib.request.Request(url, headers=AUTH_HEADER, method=method, data=body)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        err = e.read().decode('utf-8')
        print(f"HTTPError on {method} {path}: {e.code} - {err}")
        raise

# 1. 获取现有标签
tags_res = api_call('/api/v1/wx/tags')
tags = tags_res.get('data', {}).get('list', [])

sasac_mps = None
univ_mps = None

for t in tags:
    if '国资' in t['name']:
        sasac_mps = t['mps_id']
    elif '大学' in t['name']:
        univ_mps = t['mps_id']

if not sasac_mps or not univ_mps:
    print("未能完整获取国资委或大学就业标签")
    sys.exit(1)

print(f"获取到国资委公众号: {len(json.loads(sasac_mps))} 个")
print(f"获取到大学就业公众号: {len(json.loads(univ_mps))} 个")

# 2. 检查现有任务
tasks_res = api_call('/api/v1/wx/message_tasks')
tasks = tasks_res.get('data', {}).get('list', [])

# 停用或更新原来的 8 点全局任务
for task in tasks:
    if task['name'] == '8 点定时任务' and task['status'] == 1:
        print(f"停用原全局任务: {task['name']} ({task['id']})")
        api_call(f"/api/v1/wx/message_tasks/{task['id']}", method='PUT', data={
            "name": task['name'],
            "message_type": task['message_type'],
            "message_template": task['message_template'],
            "web_hook_url": task['web_hook_url'],
            "headers": task['headers'],
            "cookies": task['cookies'],
            "mps_id": task['mps_id'],
            "status": 0, # 停用
            "cron_exp": task['cron_exp']
        })

# 3. 创建/更新 任务 1：全国省级国资委-早间更新 (08:30)
task1_name = "全国省级国资委-早间更新"
task1_data = {
    "name": task1_name,
    "message_type": 0,
    "message_template": "",
    "web_hook_url": "",
    "headers": "",
    "cookies": "",
    "mps_id": sasac_mps,
    "status": 1,
    "cron_exp": "30 8 * * *"
}

existing_task1 = next((t for t in tasks if t['name'] == task1_name), None)
if existing_task1:
    print(f"更新已有任务: {task1_name}")
    res1 = api_call(f"/api/v1/wx/message_tasks/{existing_task1['id']}", method='PUT', data=task1_data)
else:
    print(f"创建新任务: {task1_name}")
    res1 = api_call("/api/v1/wx/message_tasks", method='POST', data=task1_data)

# 4. 创建/更新 任务 2：大学就业中心-午间更新 (11:30)
task2_name = "大学就业中心-午间更新"
task2_data = {
    "name": task2_name,
    "message_type": 0,
    "message_template": "",
    "web_hook_url": "",
    "headers": "",
    "cookies": "",
    "mps_id": univ_mps,
    "status": 1,
    "cron_exp": "30 11 * * *"
}

existing_task2 = next((t for t in tasks if t['name'] == task2_name), None)
if existing_task2:
    print(f"更新已有任务: {task2_name}")
    res2 = api_call(f"/api/v1/wx/message_tasks/{existing_task2['id']}", method='PUT', data=task2_data)
else:
    print(f"创建新任务: {task2_name}")
    res2 = api_call("/api/v1/wx/message_tasks", method='POST', data=task2_data)

# 5. 应用生效 (Fresh jobs)
print("调用 /api/v1/wx/message_tasks/job/fresh 应用调度...")
fresh_res = api_call("/api/v1/wx/message_tasks/job/fresh", method='PUT')
print("调度刷新响应:", fresh_res)

# 6. 检查当前调度器状态与 jobs 列表
sched_res = api_call("/api/v1/wx/task-queue/scheduler/status")
print("调度器状态:", sched_res.get('data'))

jobs_res = api_call("/api/v1/wx/task-queue/scheduler/jobs")
print("当前运行任务列表:")
for j in jobs_res.get('data', []):
    print(f"  - 任务 ID: {j.get('id')}, 名称: {j.get('name')}, 下次执行: {j.get('next_run_time')}")

