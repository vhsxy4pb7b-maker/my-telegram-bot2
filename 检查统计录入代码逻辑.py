"""
检查统计录入代码逻辑，找出金额可能丢失的原因
"""
import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# 设置输出编码为UTF-8（Windows）
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 确保项目根目录在 Python 路径中
project_root = Path(__file__).parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.date_helpers import get_daily_period_date
import db_operations

async def analyze_stats_logic():
    """分析统计录入代码逻辑"""
    
    date = get_daily_period_date()
    
    print("=" * 100)
    print("🔍 统计录入代码逻辑分析")
    print("=" * 100)
    print()
    
    # 1. 检查完成订单的收入记录和统计
    print("[1] 检查完成订单的收入记录和统计...")
    print("-" * 100)
    
    # 查询收入明细
    completed_records = await db_operations.get_income_records(date, date, type='completed')
    total_from_records = sum(r.get('amount', 0) or 0 for r in completed_records)
    
    print(f"收入明细记录数: {len(completed_records)}")
    print(f"收入明细总金额: {total_from_records:,.2f}")
    
    # 查询统计数据
    stats = await db_operations.get_stats_by_date_range(date, date, None)
    stats_completed = stats.get('completed_amount', 0)
    
    print(f"统计表总金额: {stats_completed:,.2f}")
    print(f"差异: {total_from_records - stats_completed:,.2f}")
    print()
    
    # 2. 检查按归属ID分组的情况
    print("[2] 检查按归属ID分组的统计...")
    print("-" * 100)
    
    # 按归属ID分组统计收入明细
    by_group = {}
    for record in completed_records:
        group_id = record.get('group_id')
        group_key = group_id if group_id else 'NULL'
        amount = record.get('amount', 0) or 0
        
        if group_key not in by_group:
            by_group[group_key] = {
                'count': 0,
                'total': 0.0,
                'records': []
            }
        by_group[group_key]['count'] += 1
        by_group[group_key]['total'] += amount
        by_group[group_key]['records'].append(record)
    
    # 获取所有归属ID
    all_group_ids = await db_operations.get_all_group_ids()
    
    # 检查每个归属ID的统计
    print("\n按归属ID对比:")
    for group_key in sorted(by_group.keys(), key=lambda x: (x == 'NULL', x)):
        records_total = by_group[group_key]['total']
        records_count = by_group[group_key]['count']
        
        # 查询该归属ID的统计
        if group_key == 'NULL':
            group_stats = stats
            group_display = "全局 (NULL)"
        else:
            group_stats = await db_operations.get_stats_by_date_range(date, date, group_key)
            group_display = group_key
        
        stats_total = group_stats.get('completed_amount', 0)
        diff = records_total - stats_total
        
        print(f"\n{group_display}:")
        print(f"  收入明细: {records_count} 笔, {records_total:,.2f} 元")
        print(f"  统计表: {stats_total:,.2f} 元")
        print(f"  差异: {diff:,.2f} 元", end="")
        if abs(diff) > 0.01:
            print(f" ⚠️ 不一致!")
        else:
            print(" ✅ 一致")
    
    # 3. 检查 update_all_stats 的逻辑问题
    print()
    print("=" * 100)
    print("[3] 分析 update_all_stats 逻辑...")
    print("=" * 100)
    print()
    
    print("update_all_stats 函数的更新流程：")
    print()
    print("1. 更新全局数据 (financial_data):")
    print("   - field='completed' → 'completed_amount'")
    print("   - amount 累加到全局统计")
    print()
    print("2. 更新日结数据 (daily_data):")
    print("   - 全局日结: group_id=None")
    print("   - field='completed' → 'completed_amount'")
    print("   - amount 累加到全局日结统计")
    print()
    print("3. 如果有 group_id，更新分组数据:")
    print("   - 分组日结: group_id=具体值")
    print("   - field='completed' → 'completed_amount'")
    print("   - amount 累加到分组日结统计")
    print()
    print("   - 分组累计: grouped_data")
    print("   - field='completed' → 'completed_amount'")
    print("   - amount 累加到分组累计统计")
    print()
    
    # 4. 检查可能的问题点
    print("=" * 100)
    print("[4] 可能的问题点分析...")
    print("=" * 100)
    print()
    
    print("问题1: 事务处理")
    print("  - update_financial_data: 使用 @db_transaction 装饰器")
    print("  - update_daily_data: 使用 @db_transaction 装饰器")
    print("  - 如果某个更新失败，可能导致部分更新成功，部分失败")
    print()
    
    print("问题2: 异常处理")
    print("  - update_all_stats 函数没有 try-except")
    print("  - 如果某个更新抛出异常，后续更新不会执行")
    print("  - 可能导致：")
    print("    ✓ 全局数据已更新")
    print("    ✗ 日结数据未更新")
    print("    ✗ 分组数据未更新")
    print()
    
    print("问题3: 日期问题")
    print("  - update_all_stats 使用 get_daily_period_date() 获取日期")
    print("  - record_income 也使用 get_daily_period_date() 获取日期")
    print("  - 如果日期不匹配，统计会写入错误的日期")
    print()
    
    print("问题4: 分组更新顺序")
    print("  - 先更新全局 (group_id=None)")
    print("  - 再更新分组 (group_id=具体值)")
    print("  - 如果分组更新失败，全局已更新，但分组未更新")
    print()
    
    print("问题5: 字段映射错误")
    print("  - field='completed' → daily_amount_field='completed_amount'")
    print("  - 如果字段名映射错误，可能更新到错误的字段")
    print()
    
    # 5. 检查实际数据
    print("=" * 100)
    print("[5] 检查实际数据...")
    print("=" * 100)
    print()
    
    # 检查 daily_data 表的原始记录
    daily_data = await db_operations.get_daily_data(date, None)
    print(f"全局 daily_data 记录:")
    print(f"  日期: {daily_data.get('date', 'N/A')}")
    print(f"  完成订单金额: {daily_data.get('completed_amount', 0):,.2f}")
    print()
    
    # 检查所有分组的 daily_data
    for group_id in all_group_ids:
        group_daily = await db_operations.get_daily_data(date, group_id)
        completed = group_daily.get('completed_amount', 0)
        if completed > 0:
            print(f"分组 {group_id} daily_data:")
            print(f"  完成订单金额: {completed:,.2f}")
    
    print()
    print("=" * 100)
    print("分析完成")
    print("=" * 100)

if __name__ == "__main__":
    print("脚本开始运行...", flush=True)
    try:
        asyncio.run(analyze_stats_logic())
        print("\n脚本执行完成", flush=True)
    except KeyboardInterrupt:
        print("\n已取消", flush=True)
        sys.exit(0)
    except Exception as e:
        print(f"❌ 运行时错误: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)

