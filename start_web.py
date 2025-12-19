#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动Web服务的脚本
"""

import os
import sys


def main():
    print("🚀 启动小红书数据采集Web服务...")
    print("=" * 50)

    # 检查依赖
    try:
        import flask
        import flask_cors

        print("✅ Flask依赖检查通过")
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请运行: pip install flask flask-cors")
        return

    # 检查.env文件
    if not os.path.exists(".env"):
        print("❌ 未找到.env文件，请先配置Cookie")
        print("请在.env文件中添加:")
        print("COOKIES=你的小红书Cookie")
        return

    print("✅ 环境检查通过")
    print("🌐 启动Web服务...")
    print("📱 访问地址: http://localhost:8888")
    print("=" * 50)

    # 启动服务
    from web_spider import app

    app.run(debug=True, host="0.0.0.0", port=8888)


if __name__ == "__main__":
    main()
