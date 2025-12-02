"""
列出指定日期的所有收入明细记录
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


async def list_all_income_records(date: str):
    """列出指定日期的所有收入明细记录"""
    print("=" * 100)
    print(f"{date} 所有收入明细记录")
    print("=" * 100)
    
    # 获取所有收入明细记录
    records = await db_operations.get_income_records(date, date)
    
    if not records:
        print(f"\n❌ {date} 没有收入明细记录")
        return
    
    print(f"\n总计: {len(records)} 条记录\n")
    print("-" * 100)
    
    # 按类型和创建时间排序
    records_sorted = sorted(records, key=lambda x: (
        x.get('type', ''),
        x.get('created_at', '')
    ))
    
    # 按类型分组显示
    by_type = {}
    for record in records_sorted:
        income_type = record.get('type', 'unknown')
        if income_type not in by_type:
            by_type[income_type] = []
        by_type[income_type].append(record)
    
    # 类型中文名称
    type_names = {
        'interest': '利息收入',
        'completed': '订单完成',
        'breach_end': '违约完成',
        'principal_reduction': '本金减少',
        'adjustment': '调整'
    }
    
    total_amount = 0.0
    
    for income_type in sorted(by_type.keys()):
        type_records = by_type[income_type]
        type_name = type_names.get(income_type, income_type)
        type_total = sum(r.get('amount', 0) for r in type_records)
        total_amount += type_total
        
        print(f"\n【{type_name}】{len(type_records)} 笔, 总计: {type_total:,.2f} 元")
        print("-" * 120)
        print(f"{'序号':>4} {'金额':>15} | {'订单号':>25} | {'时间':>10}")
        print("-" * 120)
        
        # 按创建时间排序（最新的在前）
        type_records_sorted = sorted(type_records, key=lambda x: x.get('created_at', ''), reverse=True)
        
        # 记录当前类型的起始序号
        type_start_num = 1 if income_type == sorted(by_type.keys())[0] else sum(len(by_type[k]) for k in sorted(by_type.keys())[:sorted(by_type.keys()).index(income_type)])
        
        for i, record in enumerate(type_records_sorted, 1):
            record_id = record.get('id', 'N/A')
            amount = record.get('amount', 0)
            order_id = record.get('order_id', None)
            group_id = record.get('group_id', None)
            customer = record.get('customer', None)
            date_str = record.get('date', 'N/A')
            created_at = record.get('created_at', 'N/A')
            note = record.get('note', None)
            created_by = record.get('created_by', None)
            
            # 格式化显示
            order_display = order_id if order_id else '无'
            group_display = group_id if group_id else 'NULL (全局)'
            customer_display = customer if customer else '无'
            note_display = note if note else '无'
            
            # 格式化时间（只显示时:分:秒）
            time_str = "无时间"
            if created_at and created_at != 'N/A':
                try:
                    if 'T' in created_at:
                        time_part = created_at.split('T')[1].split('+')[0].split('.')[0]
                        if len(time_part) >= 8:
                            time_str = time_part[11:19] if len(time_part) > 10 else time_part[:8]  # HH:MM:SS
                    elif ' ' in created_at:
                        time_str = created_at.split(' ')[1].split('.')[0][:8] if ' ' in created_at else created_at
                except:
                    time_str = created_at[:19].split(' ')[1] if ' ' in created_at else created_at
            
            # 格式化归属ID显示
            group_display = group_id if group_id else '全局'
            
            # 简洁格式输出：序号 | 金额 | 订单号 | 时间
            print(f"{i:>3}. {amount:>14,.2f} | {order_display:>25} | {time_str:>10}")
            
            # 详细格式（注释掉，需要时取消注释）
            # print(f"\n{i}. ID: {record_id}")
            # print(f"   金额: {amount:,.2f} 元")
            # print(f"   订单号: {order_display}")
            # print(f"   归属ID: {group_display}")
            # print(f"   客户类型: {customer_display}")
            # print(f"   日期: {date_str}")
            # print(f"   创建时间: {created_at}")
            # print(f"   备注: {note_display}")
            # if created_by:
            #     print(f"   创建人: {created_by}")
    
    print("\n" + "=" * 100)
    print(f"总计: {len(records)} 条记录, 总金额: {total_amount:,.2f} 元")
    print("=" * 100)
    
    # 按归属ID统计
    print("\n\n按归属ID统计:")
    print("-" * 100)
    by_group = {}
    for record in records:
        group_id = record.get('group_id', None)
        group_key = group_id if group_id else 'NULL'
        if group_key not in by_group:
            by_group[group_key] = {'count': 0, 'total': 0.0}
        by_group[group_key]['count'] += 1
        by_group[group_key]['total'] += record.get('amount', 0)
    
    for group_id in sorted(by_group.keys(), key=lambda x: (x == 'NULL', x or '')):
        stats = by_group[group_id]
        group_display = group_id if group_id else 'NULL (全局)'
        print(f"  {group_display}: {stats['count']} 笔, {stats['total']:,.2f} 元")


async def main():
    """主函数"""
    try:
        # 显示数据库路径信息
        data_dir = os.getenv('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(data_dir, 'loan_bot.db')
        print(f"\n数据库路径: {db_path}")
        print(f"DATA_DIR: {data_dir}")
        if os.path.exists(db_path):
            file_size = os.path.getsize(db_path) / 1024 / 1024
            print(f"数据库文件大小: {file_size:.2f} MB\n")
        else:
            print(f"⚠️  数据库文件不存在\n")
        
        # 支持命令行参数指定日期
        if len(sys.argv) > 1:
            date = sys.argv[1]
        else:
            date = "2025-12-02"
        
        await list_all_income_records(date)
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n已取消")
        sys.exit(0)
    except Exception as e:
        print(f"❌ 运行时错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

