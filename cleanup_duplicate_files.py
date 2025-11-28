"""清理根目录下的重复文件"""
import os
from pathlib import Path

# 需要删除的重复文件列表
duplicate_files = [
    # Handlers
    'amount_handlers.py',
    'attribution_handlers.py',
    'broadcast_handlers.py',
    'command_handlers.py',
    'order_handlers.py',
    'report_handlers.py',
    'schedule_handlers.py',
    'search_handlers.py',

    # Callbacks
    'order_callbacks.py',
    'search_callbacks.py',
    'main_callback.py',

    # Helpers
    'order_helpers.py',
    'chat_helpers.py',

    # Other
    '__init__.py',  # 根目录不应有此文件
]


def cleanup_duplicates():
    """清理重复文件"""
    project_root = Path(__file__).parent
    deleted = []
    not_found = []

    print("开始清理重复文件...")
    print("=" * 60)

    for filename in duplicate_files:
        file_path = project_root / filename

        if file_path.exists():
            # 检查对应的正确位置文件是否存在
            if filename.startswith(('amount_', 'attribution_', 'broadcast_', 'command_', 'order_', 'report_', 'schedule_', 'search_')):
                correct_path = project_root / 'handlers' / filename
            elif filename.endswith('_callbacks.py') or filename == 'main_callback.py':
                correct_path = project_root / 'callbacks' / filename
            elif filename.endswith('_helpers.py'):
                correct_path = project_root / 'utils' / filename
            else:
                correct_path = None

            # 如果正确位置的文件存在，删除根目录的重复文件
            if correct_path and correct_path.exists():
                try:
                    file_path.unlink()
                    deleted.append(filename)
                    print(f"[OK] 已删除: {filename}")
                except Exception as e:
                    print(f"[ERROR] 删除 {filename} 失败: {e}")
            elif correct_path:
                print(f"[WARN] {filename} 的对应文件不存在: {correct_path}")
            else:
                # 对于 __init__.py，直接删除
                try:
                    file_path.unlink()
                    deleted.append(filename)
                    print(f"[OK] 已删除: {filename}")
                except Exception as e:
                    print(f"[ERROR] 删除 {filename} 失败: {e}")
        else:
            not_found.append(filename)

    print("=" * 60)
    print(f"\n清理完成:")
    print(f"  已删除: {len(deleted)} 个文件")
    print(f"  未找到: {len(not_found)} 个文件")

    if deleted:
        print(f"\n已删除的文件:")
        for f in deleted:
            print(f"  - {f}")

    if not_found:
        print(f"\n未找到的文件（可能已删除）:")
        for f in not_found:
            print(f"  - {f}")


if __name__ == '__main__':
    cleanup_duplicates()
