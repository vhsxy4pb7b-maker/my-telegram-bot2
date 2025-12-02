#!/bin/bash
# 检查语法错误的脚本

echo "检查 income_handlers.py 语法..."
python3 -m py_compile handlers/income_handlers.py

if [ $? -eq 0 ]; then
    echo "✅ 语法检查通过"
else
    echo "❌ 语法错误，请检查代码"
    exit 1
fi

