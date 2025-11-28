"""数据库相关工具函数"""
import os
import sqlite3
import logging

logger = logging.getLogger(__name__)


def import_database_backup(backup_file: str, db_path: str) -> bool:
    """
    导入数据库备份文件
    
    Args:
        backup_file: 备份文件路径
        db_path: 目标数据库路径
    
    Returns:
        bool: 是否成功导入
    """
    try:
        # 确保数据库目录存在
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        with open(backup_file, 'r', encoding='utf-8') as f:
            sql_script = f.read()

        cursor.executescript(sql_script)
        conn.commit()
        conn.close()

        logger.info("数据库备份导入成功")
        return True
    except Exception as e:
        logger.error(f"导入数据库备份失败: {e}", exc_info=True)
        return False


def is_database_empty(db_path: str) -> bool:
    """
    检查数据库是否为空（没有表）
    
    Args:
        db_path: 数据库文件路径
    
    Returns:
        bool: 如果数据库为空返回True，否则返回False
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        table_count = cursor.fetchone()[0]
        conn.close()
        return table_count == 0
    except Exception as e:
        logger.debug(f"检查数据库状态时出错: {e}")
        return False

