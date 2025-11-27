"""在部署环境中导入 SQL 文件到数据库"""
import sqlite3
import os
import sys

def import_sql_file(db_path, sql_file):
    """从 SQL 文件导入数据到数据库"""
    if not os.path.exists(sql_file):
        print(f"[ERROR] 错误: 找不到 SQL 文件: {sql_file}")
        return False
    
    try:
        # 确保数据库目录存在
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print(f"[INFO] 读取 SQL 文件: {sql_file}")
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        print(f"[INFO] 导入数据到: {db_path}")
        # 执行 SQL 脚本
        cursor.executescript(sql_script)
        conn.commit()
        conn.close()
        
        print(f"[OK] 数据已成功导入到: {db_path}")
        return True
    except Exception as e:
        print(f"[ERROR] 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    # 从环境变量获取数据库路径
    data_dir = os.getenv('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(data_dir, 'loan_bot.db')
    sql_file = 'database_backup.sql'
    
    # 如果提供了命令行参数
    if len(sys.argv) > 1:
        sql_file = sys.argv[1]
    if len(sys.argv) > 2:
        db_path = sys.argv[2]
    
    print(f"[INFO] 开始导入数据库...")
    print(f"   SQL 文件: {sql_file}")
    print(f"   目标数据库: {db_path}")
    print(f"   DATA_DIR: {os.getenv('DATA_DIR', '未设置（使用默认路径）')}")
    print()
    
    if import_sql_file(db_path, sql_file):
        print()
        print("[OK] 导入完成！")
        print("[TIP] 提示: 可以重启应用以验证数据")
    else:
        sys.exit(1)

