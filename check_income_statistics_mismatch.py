"""
检查收入明细记录和统计数据的不一致问题
用于诊断生产环境中实际记录金额和统计记录金额不一致的原因
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

# 立即输出测试
print("脚本已加载，准备执行...", flush=True)

async def check_income_mismatch(date: str = None):
    """检查指定日期的收入明细和统计数据是否一致"""
    import sys
    sys.stdout.flush()  # 确保输出立即显示
    
    if date is None:
        date = get_daily_period_date()
    
    print("=" * 80, flush=True)
    print(f"检查日期: {date}", flush=True)
    print("=" * 80, flush=True)
    
    # 1. 获取收入明细记录
    print("\n[1] 查询收入明细记录...")
    income_records = await db_operations.get_income_records(date, date)
    
    print(f"收入明细记录总数: {len(income_records)} 条")
    
    # 按类型分组统计
    by_type = {}
    by_group = {}  # 按归属ID分组统计
    
    for record in income_records:
        income_type = record.get('type', 'unknown')
        group_id = record.get('group_id', 'NULL')
        
        if income_type not in by_type:
            by_type[income_type] = {
                'count': 0,
                'total': 0.0,
                'records': []
            }
        by_type[income_type]['count'] += 1
        by_type[income_type]['total'] += record.get('amount', 0)
        by_type[income_type]['records'].append(record)
        
        # 按归属ID分组
        if group_id not in by_group:
            by_group[group_id] = {
                'count': 0,
                'total': 0.0,
                'records': []
            }
        by_group[group_id]['count'] += 1
        by_group[group_id]['total'] += record.get('amount', 0)
        by_group[group_id]['records'].append(record)
    
    print("\n收入明细按类型统计:")
    print("-" * 80)
    for income_type, stats in sorted(by_type.items()):
        print(f"  {income_type}: {stats['count']} 笔, 总计: {stats['total']:,.2f}")
    total_from_records = sum(stats['total'] for stats in by_type.values())
    print(f"\n收入明细总计: {total_from_records:,.2f}")
    
    # 按归属ID分组统计
    print("\n收入明细按归属ID统计:")
    print("-" * 80)
    # 排序时处理 None 值
    def sort_key(item):
        key = item[0]
        return (key is None, key or '')
    
    for group_id, stats in sorted(by_group.items(), key=sort_key):
        group_display = group_id if group_id else 'NULL (全局)'
        print(f"  {group_display}: {stats['count']} 笔, 总计: {stats['total']:,.2f}")
    
    # 2. 获取统计数据
    print("\n[2] 查询统计数据 (daily_data)...")
    stats = await db_operations.get_stats_by_date_range(date, date, None)
    
    print("\n统计数据 (daily_data):")
    print("-" * 80)
    print(f"  利息收入 (interest): {stats.get('interest', 0):,.2f}")
    print(f"  完成订单金额 (completed_amount): {stats.get('completed_amount', 0):,.2f}")
    print(f"  违约完成金额 (breach_end_amount): {stats.get('breach_end_amount', 0):,.2f}")
    
    # 计算统计数据总和（不包括本金减少，因为统计表中没有本金减少字段）
    total_from_stats = (
        stats.get('interest', 0) +
        stats.get('completed_amount', 0) +
        stats.get('breach_end_amount', 0)
    )
    print(f"\n统计数据总计 (interest + completed + breach_end): {total_from_stats:,.2f}")
    
    # 3. 按归属ID分组对比分析
    print("\n[3] 按归属ID分组对比分析...")
    print("-" * 80)
    
    # 按归属ID分组统计利息收入记录
    interest_by_group = {}
    interest_records = by_type.get('interest', {}).get('records', [])
    for record in interest_records:
        group_id = record.get('group_id', None)
        group_key = group_id if group_id else 'NULL'
        if group_key not in interest_by_group:
            interest_by_group[group_key] = {
                'count': 0,
                'total': 0.0,
                'records': []
            }
        interest_by_group[group_key]['count'] += 1
        interest_by_group[group_key]['total'] += record.get('amount', 0)
        interest_by_group[group_key]['records'].append(record)
    
    # 对比每个归属ID的统计数据
    all_group_ids = await db_operations.get_all_group_ids()
    all_group_ids.append(None)  # 添加全局（NULL）
    
    print("\n各归属ID的利息收入对比:")
    print("-" * 80)
    total_diff = 0.0
    
    for group_id in sorted(all_group_ids, key=lambda x: (x is None, x or '')):
        group_key = group_id if group_id else 'NULL'
        group_display = group_id if group_id else 'NULL (全局)'
        
        # 收入明细中的金额
        records_total = interest_by_group.get(group_key, {}).get('total', 0)
        records_count = interest_by_group.get(group_key, {}).get('count', 0)
        
        # 统计表中的金额
        if group_id:
            group_stats = await db_operations.get_stats_by_date_range(date, date, group_id)
        else:
            group_stats = stats
        
        stats_interest = group_stats.get('interest', 0)
        diff = records_total - stats_interest
        
        print(f"\n{group_display}:")
        print(f"  收入明细: {records_count} 笔, {records_total:,.2f} 元")
        print(f"  统计表: {stats_interest:,.2f} 元")
        print(f"  差异: {diff:,.2f} 元", end="")
        
        if abs(diff) > 0.01:
            print(f"  ⚠️ 不一致!", end="")
            if diff > 0:
                print(f" (收入明细多 {diff:,.2f})")
            else:
                print(f" (统计表多 {abs(diff):,.2f})")
        else:
            print(" ✅ 一致")
        
        total_diff += diff
    
    # 总体对比
    print("\n" + "-" * 80)
    interest_from_records = by_type.get('interest', {}).get('total', 0)
    interest_from_stats = stats.get('interest', 0)
    interest_diff = interest_from_records - interest_from_stats
    
    print(f"\n总计对比:")
    print(f"  收入明细总计: {interest_from_records:,.2f} (所有归属ID合计)")
    print(f"  统计表总计 (全局): {interest_from_stats:,.2f}")
    print(f"  总差异: {interest_diff:,.2f}")
    if abs(interest_diff) > 0.01:
        print(f"  ⚠️ 不一致!")
    
    # 对比完成订单
    completed_from_records = by_type.get('completed', {}).get('total', 0)
    completed_from_stats = stats.get('completed_amount', 0)
    completed_diff = completed_from_records - completed_from_stats
    
    print(f"\n完成订单金额:")
    print(f"  收入明细: {completed_from_records:,.2f}")
    print(f"  统计数据: {completed_from_stats:,.2f}")
    print(f"  差异: {completed_diff:,.2f}")
    if abs(completed_diff) > 0.01:
        print(f"  ⚠️ 不一致!")
    
    # 对比违约完成
    breach_end_from_records = by_type.get('breach_end', {}).get('total', 0)
    breach_end_from_stats = stats.get('breach_end_amount', 0)
    breach_end_diff = breach_end_from_records - breach_end_from_stats
    
    print(f"\n违约完成金额:")
    print(f"  收入明细: {breach_end_from_records:,.2f}")
    print(f"  统计数据: {breach_end_from_stats:,.2f}")
    print(f"  差异: {breach_end_diff:,.2f}")
    if abs(breach_end_diff) > 0.01:
        print(f"  ⚠️ 不一致!")
    
    # 本金减少（只在收入明细中有，统计表中没有）
    principal_reduction = by_type.get('principal_reduction', {}).get('total', 0)
    if principal_reduction > 0:
        print(f"\n本金减少:")
        print(f"  收入明细: {principal_reduction:,.2f}")
        print(f"  统计数据: (无此字段)")
        print(f"  注意: 本金减少不在统计表中")
    
    # 4. 详细分析不一致的原因
    print("\n[4] 详细分析...")
    print("-" * 80)
    
    if abs(interest_diff) > 0.01:
        print(f"\n利息收入不一致原因分析:")
        print(f"  差异: {interest_diff:,.2f}")
        if interest_diff > 0:
            print(f"  → 收入明细中有 {interest_diff:,.2f} 的利息收入未更新到统计表")
            print(f"  可能原因:")
            print(f"    1. record_income() 执行成功，但 update_all_stats() 执行失败")
            print(f"    2. 记录时使用了错误的日期")
            print(f"    3. 统计表被手动修改或重置")
            print(f"\n  未同步的利息收入记录（全部52条）:")
            interest_records = by_type.get('interest', {}).get('records', [])
            # 按创建时间排序，显示序号
            interest_records_sorted = sorted(interest_records, key=lambda x: x.get('created_at', ''))
            for i, record in enumerate(interest_records_sorted, 1):
                group_id = record.get('group_id', None)
                group_display = group_id if group_id else 'NULL (全局)'
                print(f"    {i}. 金额: {record.get('amount', 0):,.2f}, "
                      f"订单号: {record.get('order_id', '无')}, "
                      f"归属ID: {group_display}, "
                      f"日期: {record.get('date', 'N/A')}, "
                      f"创建时间: {record.get('created_at', 'N/A')}")
            
            # 按归属ID分组统计
            print(f"\n  按归属ID分组的利息收入记录:")
            interest_by_group = {}
            for record in interest_records:
                group_id = record.get('group_id', None)
                group_key = group_id if group_id else 'NULL'
                if group_key not in interest_by_group:
                    interest_by_group[group_key] = []
                interest_by_group[group_key].append(record)
            
            for group_id in sorted(interest_by_group.keys(), key=lambda x: (x == 'NULL', x)):
                group_records = interest_by_group[group_id]
                group_total = sum(r.get('amount', 0) for r in group_records)
                group_display = group_id if group_id else 'NULL (全局)'
                print(f"    {group_display}: {len(group_records)} 条, 总计: {group_total:,.2f}")
        else:
            print(f"  → 统计表中的利息收入比收入明细多 {abs(interest_diff):,.2f}")
            print(f"  可能原因:")
            print(f"    1. 统计表中有历史数据或手动修改的数据")
            print(f"    2. 某些记录被删除但统计未更新")
    
    if abs(completed_diff) > 0.01:
        print(f"\n完成订单金额不一致原因分析:")
        print(f"  差异: {completed_diff:,.2f}")
        if completed_diff > 0:
            print(f"  → 收入明细中有 {completed_diff:,.2f} 的完成订单金额未更新到统计表")
        else:
            print(f"  → 统计表中的完成订单金额比收入明细多 {abs(completed_diff):,.2f}")
    
    if abs(breach_end_diff) > 0.01:
        print(f"\n违约完成金额不一致原因分析:")
        print(f"  差异: {breach_end_diff:,.2f}")
        if breach_end_diff > 0:
            print(f"  → 收入明细中有 {breach_end_diff:,.2f} 的违约完成金额未更新到统计表")
        else:
            print(f"  → 统计表中的违约完成金额比收入明细多 {abs(breach_end_diff):,.2f}")
    
    # 5. 检查 daily_data 表中的原始记录
    print("\n[5] 检查 daily_data 表中的原始记录...")
    print("-" * 80)
    daily_data = await db_operations.get_daily_data(date, None)
    
    print(f"daily_data 表记录:")
    print(f"  date: {daily_data.get('date', 'N/A')}")
    print(f"  group_id: {daily_data.get('group_id', 'NULL (全局)')}")
    print(f"  interest: {daily_data.get('interest', 0):,.2f}")
    print(f"  completed_amount: {daily_data.get('completed_amount', 0):,.2f}")
    print(f"  breach_end_amount: {daily_data.get('breach_end_amount', 0):,.2f}")
    
    # 检查是否有多条记录（可能有分组数据）
    print("\n检查是否有分组数据...")
    # 获取所有分组ID
    all_groups = await db_operations.get_all_group_ids()
    for group_id in all_groups:
        group_daily = await db_operations.get_daily_data(date, group_id)
        if group_daily.get('interest', 0) > 0 or group_daily.get('completed_amount', 0) > 0 or group_daily.get('breach_end_amount', 0) > 0:
            print(f"  分组 {group_id}:")
            print(f"    interest: {group_daily.get('interest', 0):,.2f}")
            print(f"    completed_amount: {group_daily.get('completed_amount', 0):,.2f}")
            print(f"    breach_end_amount: {group_daily.get('breach_end_amount', 0):,.2f}")
    
    print("\n" + "=" * 80)
    print("检查完成")
    print("=" * 80)


async def check_date_range(start_date: str, end_date: str):
    """检查日期范围内的收入明细和统计数据"""
    print("=" * 80)
    print(f"检查日期范围: {start_date} 至 {end_date}")
    print("=" * 80)
    
    # 获取收入明细记录
    income_records = await db_operations.get_income_records(start_date, end_date)
    
    # 按类型分组统计
    by_type = {}
    for record in income_records:
        income_type = record.get('type', 'unknown')
        if income_type not in by_type:
            by_type[income_type] = {'count': 0, 'total': 0.0}
        by_type[income_type]['count'] += 1
        by_type[income_type]['total'] += record.get('amount', 0)
    
    print("\n收入明细按类型统计:")
    for income_type, stats in sorted(by_type.items()):
        print(f"  {income_type}: {stats['count']} 笔, 总计: {stats['total']:,.2f}")
    
    # 获取统计数据
    stats = await db_operations.get_stats_by_date_range(start_date, end_date, None)
    
    print("\n统计数据:")
    print(f"  利息收入: {stats.get('interest', 0):,.2f}")
    print(f"  完成订单金额: {stats.get('completed_amount', 0):,.2f}")
    print(f"  违约完成金额: {stats.get('breach_end_amount', 0):,.2f}")
    
    # 对比
    interest_diff = by_type.get('interest', {}).get('total', 0) - stats.get('interest', 0)
    completed_diff = by_type.get('completed', {}).get('total', 0) - stats.get('completed_amount', 0)
    breach_end_diff = by_type.get('breach_end', {}).get('total', 0) - stats.get('breach_end_amount', 0)
    
    print("\n差异:")
    print(f"  利息收入差异: {interest_diff:,.2f}")
    print(f"  完成订单金额差异: {completed_diff:,.2f}")
    print(f"  违约完成金额差异: {breach_end_diff:,.2f}")


async def main():
    """主函数"""
    print("脚本开始运行...", flush=True)
    try:
        print("检查数据库连接...", flush=True)
        # 测试数据库连接
        test_data = await db_operations.get_financial_data()
        print(f"数据库连接成功，流动资金: {test_data.get('liquid_funds', 0):,.2f}", flush=True)
        
        if len(sys.argv) > 1:
            if sys.argv[1] == '--range' and len(sys.argv) >= 4:
                start_date = sys.argv[2]
                end_date = sys.argv[3]
                await check_date_range(start_date, end_date)
            else:
                date = sys.argv[1]
                await check_income_mismatch(date)
        else:
            # 默认检查今天
            await check_income_mismatch()
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    print("进入主程序...", flush=True)
    try:
        print("调用 asyncio.run(main())...", flush=True)
        asyncio.run(main())
        print("脚本执行完成", flush=True)
    except KeyboardInterrupt:
        print("\n已取消", flush=True)
        sys.exit(0)
    except Exception as e:
        print(f"❌ 运行时错误: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)

