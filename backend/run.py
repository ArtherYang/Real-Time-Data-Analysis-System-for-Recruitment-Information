"""
应用入口
========
启动 Flask 开发服务器。

使用方式：
    python run.py              # 默认 http://127.0.0.1:5000
    python run.py --port 8080  # 指定端口
"""

import sys
from app import create_app

if __name__ == "__main__":
    port = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == "--port" else 5000
    app = create_app()
    app.run(host="0.0.0.0", port=port, debug=True)
