#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
强制更新所有订单的星期分组
重新读取订单日期，计算星期分组，并同步到数据库
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

import db_operations
from utils.chat_helpers import get_weekday_group_from_date

async def update_all_weekday_groups():
    """强制更新所有订单的星期分组"""
    print("开始更新所有订单的星期分组...")
    print("=" * 60)
    
    # 获取所有订单（包括已完成和违约完成的）
    all_orders = await db_operations.search_orders_advanced_all_states({})
    
    if not all_orders:
        print("没有找到订单")
        return
    
    print(f"找到 {len(all_orders)} 个订单")
    print("-" * 60)
    
    updated_count = 0
    error_count = 0
    skipped_count = 0
    
    for order in all_orders:
        order_id = order['order_id']
        chat_id = order['chat_id']
        current_weekday_group = order.get('weekday_group', '')
        order_date_str = order.get('date', '')
        
        try:
            # 方法1: 从订单ID解析日期（优先）
            date_from_id = None
            if order_id.startswith('A'):
                # 新客户：A + 10位数字
                if len(order_id) >= 7 and order_id[1:7].isdigit():
                    date_part = order_id[1:7]
                    try:
                        full_date_str = f"20{date_part}"
                        date_from_id = datetime.strptime(full_date_str, "%Y%m%d").date()
                    except ValueError:
                        pass
            else:
                # 老客户：10位数字
                if len(order_id) >= 6 and order_id[:6].isdigit():
                    date_part = order_id[:6]
                    try:
                        full_date_str = f"20{date_part}"
                        date_from_id = datetime.strptime(full_date_str, "%Y%m%d").date()
                    except ValueError:
                        pass
            
            # 方法2: 从date字段解析日期
            date_from_db = None
            if order_date_str:
                try:
                    # 处理 "YYYY-MM-DD HH:MM:SS" 或 "YYYY-MM-DD" 格式
                    date_str = order_date_str.split()[0] if ' ' in order_date_str else order_date_str
                    date_from_db = datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    pass
            
            # 优先使用订单ID中的日期，如果没有则使用数据库中的日期
            order_date = date_from_id or date_from_db
            
            if not order_date:
                print(f"[SKIP] Order {order_id}: Cannot parse date")
                skipped_count += 1
                continue
            
            # 计算正确的星期分组
            correct_weekday_group = get_weekday_group_from_date(order_date)
            
            # 强制更新（即使相同也更新，确保数据一致性）
            success = await db_operations.update_order_weekday_group(chat_id, correct_weekday_group)
            
            if success:
                weekday_name = order_date.strftime('%A')
                if current_weekday_group != correct_weekday_group:
                    print(f"[UPDATED] Order {order_id}: {order_date} ({weekday_name})")
                    print(f"          '{current_weekday_group}' -> '{correct_weekday_group}'")
                updated_count += 1
            else:
                print(f"[ERROR] Order {order_id}: Update failed")
                error_count += 1
                
        except Exception as e:
            print(f"[ERROR] Order {order_id}: {e}")
            error_count += 1
    
    print("=" * 60)
    print(f"更新完成！")
    print(f"  已更新: {updated_count} 个订单")
    print(f"  跳过: {skipped_count} 个订单（无法解析日期）")
    print(f"  错误: {error_count} 个订单")
    print(f"  总计: {len(all_orders)} 个订单")
    print("=" * 60)
    
    if error_count == 0 and skipped_count == 0:
        print("SUCCESS: 所有订单的星期分组已成功更新！")
    elif error_count == 0:
        print(f"SUCCESS: {updated_count} 个订单已更新，{skipped_count} 个订单跳过")


if __name__ == "__main__":
    asyncio.run(update_all_weekday_groups())

