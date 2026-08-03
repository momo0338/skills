import os
import sys

# 把 src/ 注入 sys.path,使测试无论从哪个 cwd 运行都能 import dy_fanpai
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
