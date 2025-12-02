#!/bin/bash
# 强制更新代码并重启服务

echo "=========================================="
echo "强制更新代码并重启"
echo "=========================================="

cd /app || exit 1

echo "1️⃣ 强制拉取最新代码..."
git fetch origin
git reset --hard origin/main

echo ""
echo "2️⃣ 检查语法..."
python3 -m py_compile handlers/income_handlers.py

if [ $? -eq 0 ]; then
    echo "✅ 语法检查通过"
else
    echo "❌ 语法错误！"
    exit 1
fi

echo ""
echo "3️⃣ 显示最新提交..."
git log --oneline -3

echo ""
echo "4️⃣ 重启服务..."
# 根据你的部署方式选择：
# sudo systemctl restart loan-bot
# docker restart <container_name>
# pm2 restart loan-bot

echo "✅ 完成！"

