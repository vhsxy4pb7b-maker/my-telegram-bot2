#!/bin/bash
# 在生产服务器上运行收入明细查询脚本

# 设置日期（默认 2025-12-02）
DATE=${1:-2025-12-02}

# 检查脚本是否存在
if [ ! -f "list_all_income_records.py" ]; then
    echo "❌ 错误: 找不到脚本 list_all_income_records.py"
    echo "请确保在项目根目录运行此脚本"
    exit 1
fi

# 检查数据库路径
DATA_DIR=${DATA_DIR:-/data}
DB_PATH="$DATA_DIR/loan_bot.db"

echo "=========================================="
echo "生产环境收入明细查询"
echo "=========================================="
echo "日期: $DATE"
echo "数据库路径: $DB_PATH"
echo ""

# 检查数据库文件
if [ -f "$DB_PATH" ]; then
    echo "✅ 数据库文件存在"
    FILE_SIZE=$(du -h "$DB_PATH" | cut -f1)
    echo "   文件大小: $FILE_SIZE"
else
    echo "⚠️  数据库文件不存在: $DB_PATH"
    echo "   尝试使用默认路径..."
    DB_PATH="./loan_bot.db"
    if [ ! -f "$DB_PATH" ]; then
        echo "❌ 找不到数据库文件"
        exit 1
    fi
fi

echo ""
echo "=========================================="
echo "开始查询..."
echo "=========================================="
echo ""

# 设置环境变量（如果需要）
export DATA_DIR=$DATA_DIR

# 运行脚本
python list_all_income_records.py "$DATE"

