"""
诊断完成订单金额显示问题
检查完成订单的收入记录是否正确记录和显示
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

async def diagnose_completed_income():
    """诊断完成订单收入金额显示问题"""
    
    date = get_daily_period_date()
    
    print("=" * 100)
    print(f"🔍 诊断完成订单金额显示问题")
    print(f"日期: {date}")
    print("=" * 100)
    print()
    
    # 1. 查询所有完成订单的收入记录
    print("[1] 查询完成订单收入记录...")
    completed_records = await db_operations.get_income_records(date, date, type='completed')
    
    print(f"✅ 找到 {len(completed_records)} 条完成订单收入记录")
    print()
    
    if not completed_records:
        print("❌ 没有找到完成订单的收入记录！")
        print()
        print("可能的原因：")
        print("1. 今天没有完成任何订单")
        print("2. 完成订单时收入记录未成功写入数据库")
        print("3. 日期不匹配（记录在其他日期）")
        return
    
    # 2. 检查每条记录的金额
    print("[2] 检查每条记录的详细信息...")
    print("-" * 100)
    
    total_amount = 0.0
    zero_amount_count = 0
    null_amount_count = 0
    
    for i, record in enumerate(completed_records, 1):
        record_id = record.get('id', 'N/A')
        amount = record.get('amount')
        order_id = record.get('order_id', '无')
        group_id = record.get('group_id')
        created_at = record.get('created_at', 'N/A')
        date_str = record.get('date', 'N/A')
        
        print(f"\n记录 {i} (ID: {record_id}):")
        print(f"  订单号: {order_id}")
        print(f"  归属ID: {group_id if group_id else 'NULL (全局)'}")
        print(f"  日期: {date_str}")
        print(f"  创建时间: {created_at}")
        
        # 检查金额
        if amount is None:
            print(f"  金额: ❌ NULL (空值)")
            null_amount_count += 1
        elif amount == 0:
            print(f"  金额: ⚠️ 0.00 (零值)")
            zero_amount_count += 1
        else:
            print(f"  金额: ✅ {amount:,.2f}")
            total_amount += amount
    
    print()
    print("-" * 100)
    print(f"[3] 统计结果:")
    print(f"  总记录数: {len(completed_records)}")
    print(f"  有金额的记录: {len(completed_records) - zero_amount_count - null_amount_count}")
    print(f"  金额为 0 的记录: {zero_amount_count}")
    print(f"  金额为 NULL 的记录: {null_amount_count}")
    print(f"  总金额: {total_amount:,.2f}")
    print()
    
    # 3. 检查统计表
    print("[4] 检查统计表中的完成订单金额...")
    stats = await db_operations.get_stats_by_date_range(date, date, None)
    stats_completed = stats.get('completed_amount', 0)
    
    print(f"  统计表金额: {stats_completed:,.2f}")
    print(f"  收入明细总金额: {total_amount:,.2f}")
    diff = total_amount - stats_completed
    print(f"  差异: {diff:,.2f}")
    print()
    
    # 4. 测试格式化显示
    print("[5] 测试格式化显示...")
    print("-" * 100)
    print(f"{'时间':<8}  {'订单号':<25}  {'金额':>15}")
    print("-" * 100)
    
    for i, record in enumerate(completed_records[:5], 1):  # 只显示前5条
        amount = record.get('amount', 0)
        order_id = record.get('order_id') or '无'
        
        # 格式化时间
        time_str = "无时间"
        if record.get('created_at'):
            try:
                created_at_str = record['created_at']
                if 'T' in created_at_str:
                    time_part = created_at_str.split('T')[1].split('+')[0].split('.')[0]
                    time_str = time_part[:8] if len(time_part) >= 8 else time_part
                elif ' ' in created_at_str:
                    time_str = created_at_str.split(' ')[1].split('.')[0][:8]
            except:
                pass
        
        # 格式化金额
        if amount is None:
            amount_str = "NULL"
        else:
            amount_str = f"{amount:,.2f}"
        
        print(f"{time_str:<8}  {order_id:<25}  {amount_str:>15}")
    
    if len(completed_records) > 5:
        print(f"... (还有 {len(completed_records) - 5} 条记录)")
    print()
    
    # 5. 问题分析
    print("=" * 100)
    print("【问题分析】")
    print("=" * 100)
    print()
    
    if null_amount_count > 0:
        print(f"⚠️ 发现 {null_amount_count} 条记录的金额为 NULL")
        print("   可能原因：")
        print("   1. 数据库记录时金额字段未设置")
        print("   2. 数据库字段允许 NULL 值")
        print()
    
    if zero_amount_count > 0:
        print(f"⚠️ 发现 {zero_amount_count} 条记录的金额为 0")
        print("   可能原因：")
        print("   1. 订单金额本身为 0")
        print("   2. 记录时传入的金额为 0")
        print()
    
    if abs(diff) > 0.01:
        print(f"⚠️ 收入明细和统计表金额不一致")
        print(f"   差异: {diff:,.2f}")
        print("   建议运行 /fix_statistics 修复")
        print()
    
    if total_amount == 0 and len(completed_records) > 0:
        print("❌ 所有记录的金额都为 0 或 NULL")
        print("   这说明完成订单时金额没有正确记录")
        print("   需要检查 set_end() 函数中的 record_income() 调用")
        print()
    
    print("=" * 100)
    print("诊断完成")
    print("=" * 100)

if __name__ == "__main__":
    print("脚本开始运行...", flush=True)
    try:
        asyncio.run(diagnose_completed_income())
        print("\n脚本执行完成", flush=True)
    except KeyboardInterrupt:
        print("\n已取消", flush=True)
        sys.exit(0)
    except Exception as e:
        print(f"❌ 运行时错误: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)

