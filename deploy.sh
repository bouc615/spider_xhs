#!/bin/bash

# Amazon Linux 专用部署脚本
# 使用方法: chmod +x deploy.sh && ./deploy.sh

set -e

echo "🚀 小红书数据采集项目 - Amazon Linux 部署"
echo "============================================"

# 1. 拉取最新代码
echo "📥 拉取最新代码..."
git pull origin master || echo "⚠️ Git pull 失败，继续使用本地代码"

# 2. 更新系统
echo "📦 更新系统..."
sudo yum update -y

# 3. 安装 Docker
echo "🐳 安装 Docker..."
if ! command -v docker &> /dev/null; then
    sudo yum install -y docker
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker $USER
    echo "✅ Docker 安装完成"
    echo "⚠️  需要重新登录以应用 Docker 权限，请运行："
    echo "   logout 然后重新登录，再次执行 ./deploy.sh"
    exit 0
fi

# 4. 启动 Docker 服务
echo "🔧 启动 Docker 服务..."
sudo systemctl start docker

# 5. 创建必要目录
echo "📁 创建数据目录..."
mkdir -p datas/excel_datas datas/media_datas web_data

# 6. 创建基础 .env 文件
if [ ! -f ".env" ]; then
    echo "⚙️ 创建配置文件..."
    cat > .env << 'EOF'
# 服务配置
PORT=8888
HOST=0.0.0.0
EOF
fi

# 7. 停止旧容器
echo "🔄 清理旧容器..."
docker stop xhs-spider-app 2>/dev/null || true
docker rm xhs-spider-app 2>/dev/null || true

# 8. 构建镜像
echo "🔨 构建 Docker 镜像..."
docker build -t xhs-spider .

# 9. 启动容器
echo "🚀 启动服务..."
docker run -d \
    --name xhs-spider-app \
    --restart unless-stopped \
    -p 8888:8888 \
    -v $(pwd)/datas:/app/datas \
    -v $(pwd)/web_data:/app/web_data \
    -v $(pwd)/.env:/app/.env \
    xhs-spider python start_web.py

# 10. 等待服务启动
echo "⏳ 等待服务启动..."
sleep 5

# 11. 检查服务状态
if docker ps | grep -q xhs-spider-app; then
    echo "✅ 服务启动成功！"
else
    echo "❌ 服务启动失败，查看日志："
    docker logs xhs-spider-app
    exit 1
fi

# 12. 获取公网 IP
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s ipinfo.io/ip 2>/dev/null || echo "localhost")

# 13. 显示部署信息
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
echo "   3. 数据会自动保存到本地目录"
echo ""
echo "🔗 项目地址: https://github.com/cv-cat/Spider_XHS"
echo "=================================="