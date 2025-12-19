#!/bin/bash

# Amazon 服务器一键部署脚本 - Docker 方案
# 使用方法: chmod +x deploy.sh && ./deploy.sh

set -e

echo "🚀 小红书数据采集项目 - Amazon 服务器一键部署"
echo "================================================"

# 1. 更新系统
echo "📦 更新系统..."
sudo apt update && sudo apt upgrade -y

# 2. 安装 Docker
echo "🐳 安装 Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo "✅ Docker 安装完成"
    echo "⚠️  需要重新登录以应用 Docker 权限，请运行："
    echo "   logout 然后重新登录，再次执行 ./deploy.sh"
    exit 0
fi

# 3. 创建必要目录
echo "📁 创建数据目录..."
mkdir -p datas/excel_datas datas/media_datas web_data

# 4. 创建基础 .env 文件（如果不存在）
if [ ! -f ".env" ]; then
    echo "⚙️ 创建基础配置文件..."
    cat > .env << 'EOF'
# 服务配置
PORT=8888
HOST=0.0.0.0
EOF
fi

# 5. 停止旧容器（如果存在）
echo "🔄 清理旧容器..."
docker stop xhs-spider-app 2>/dev/null || true
docker rm xhs-spider-app 2>/dev/null || true

# 6. 构建镜像
echo "🔨 构建 Docker 镜像..."
docker build -t xhs-spider .

# 7. 启动容器
echo "🚀 启动服务..."
docker run -d \
    --name xhs-spider-app \
    --restart unless-stopped \
    -p 8888:8888 \
    -v $(pwd)/datas:/app/datas \
    -v $(pwd)/web_data:/app/web_data \
    -v $(pwd)/.env:/app/.env \
    xhs-spider python start_web.py

# 8. 配置防火墙
echo "🔥 配置防火墙..."
sudo ufw allow 8888/tcp >/dev/null 2>&1 || true
sudo ufw --force enable >/dev/null 2>&1 || true

# 9. 等待服务启动
echo "⏳ 等待服务启动..."
sleep 5

# 10. 检查服务状态
if docker ps | grep -q xhs-spider-app; then
    echo "✅ 服务启动成功！"
else
    echo "❌ 服务启动失败，查看日志："
    docker logs xhs-spider-app
    exit 1
fi

# 11. 获取公网 IP
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s ipinfo.io/ip 2>/dev/null || echo "localhost")

# 12. 显示部署信息
echo ""
echo "🎉🎉🎉 部署完成！🎉🎉🎉"
echo "=================================="
echo ""
echo "📱 访问地址: http://$PUBLIC_IP:8888"
echo ""
echo "🔧 常用命令:"
echo "   查看日志: docker logs -f xhs-spider-app"
echo "   重启服务: docker restart xhs-spider-app"
echo "   停止服务: docker stop xhs-spider-app"
echo "   进入容器: docker exec -it xhs-spider-app bash"
echo ""
echo "📁 数据目录:"
echo "   配置文件: $(pwd)/.env"
echo "   采集数据: $(pwd)/datas/"
echo "   Web数据: $(pwd)/web_data/"
echo ""
echo "⚠️  使用说明:"
echo "   1. 打开 Web 界面后，在页面上输入小红书 Cookie"
echo "   2. Cookie 获取：登录小红书 -> F12 -> Network -> 复制 Cookie"
echo "   3. 数据会自动保存到本地 datas/ 和 web_data/ 目录"
echo ""
echo "🔗 项目地址: https://github.com/cv-cat/Spider_XHS"
echo "=================================="