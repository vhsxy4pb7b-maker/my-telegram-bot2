"""导出本地数据库为 SQL 文件"""
import sqlite3
import os
import sys

def export_database(db_path, output_file):
    """导出数据库为 SQL 格式"""
    if not os.path.exists(db_path):
        print(f"错误: 找不到数据库文件: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        
        # 使用 iterdump() 方法导出
        with open(output_file, 'w', encoding='utf-8') as f:
            for line in conn.iterdump():
                f.write(f'{line}\n')
        
        conn.close()
        print(f"[OK] 数据库已成功导出到: {output_file}")
        print(f"[INFO] 文件大小: {os.path.getsize(output_file) / 1024:.2f} KB")
        return True
    except Exception as e:
        print(f"[ERROR] 导出失败: {e}")
        return False

if __name__ == '__main__':
    # 默认数据库路径
    db_path = 'loan_bot.db'
    output_file = 'database_backup.sql'
    
    # 如果提供了命令行参数
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    print(f"[INFO] 开始导出数据库...")
    print(f"   源文件: {db_path}")
    print(f"   目标文件: {output_file}")
    print()
    
    if export_database(db_path, output_file):
        print()
        print("[NEXT] 下一步:")
        print("   1. 检查 database_backup.sql 文件")
        print("   2. 将文件上传到部署环境")
        print("   3. 在部署环境中运行导入脚本")
    else:
        sys.exit(1)

