"""测试播报功能 - 订单 2507220108"""
from datetime import datetime, date
from utils.broadcast_helpers import calculate_next_payment_date, format_broadcast_message

# 订单ID: 2507220108
order_id = '2507220108'

# 解析订单信息
date_part = order_id[:6]  # 250722
amount_part = int(order_id[8:10])  # 08
amount = amount_part * 1000  # 8000

# 解析日期
full_date_str = f'20{date_part}'  # 20250722
order_date_from_id = datetime.strptime(full_date_str, '%Y%m%d').date()

print("=" * 60)
print("订单信息（从订单ID解析）")
print("=" * 60)
print(f"订单ID: {order_id}")
print(f"日期部分: {date_part}")
print(f"金额部分: {amount_part}")
print(f"解析的订单日期: {order_date_from_id} ({order_date_from_id.strftime('%A')})")
print(f"订单金额: {amount:,.0f}")

# 计算下个付款日期（使用从订单ID解析的日期）
next_date, date_str, weekday_str = calculate_next_payment_date(order_date_from_id)

print("\n" + "=" * 60)
print("下个付款日期（基于订单ID解析的日期）")
print("=" * 60)
print(f"订单日期: {order_date_from_id} ({order_date_from_id.strftime('%A')})")
print(f"下个付款日期: {date_str} ({weekday_str})")
print(f"计算: {order_date_from_id} + 7天 = {next_date.date()}")

# 生成播报消息
principal = amount
principal_12 = principal * 0.12
outstanding_interest = 0

message = format_broadcast_message(
    principal=principal,
    principal_12=principal_12,
    outstanding_interest=outstanding_interest,
    date_str=date_str,
    weekday_str=weekday_str
)

print("\n" + "=" * 60)
print("播报消息")
print("=" * 60)
print(message)
print("=" * 60)

# 如果数据库中的日期不同，也测试一下
print("\n" + "=" * 60)
print("注意：实际播报使用数据库中的订单日期字段")
print("=" * 60)
print("如果数据库中的订单日期与订单ID解析的日期不同，")
print("播报功能会使用数据库中的日期来计算下个付款日期。")

