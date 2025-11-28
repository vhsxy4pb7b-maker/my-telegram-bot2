"""测试播报功能 - 使用数据库中的订单日期"""
from datetime import datetime, date
from utils.broadcast_helpers import calculate_next_payment_date, format_broadcast_message

# 订单ID: 2505200104
order_id = '2505200104'
amount = 4000

# 假设数据库中存储的订单日期是 2025-11-25 (周二)
# 数据库中的日期格式通常是 "2025-11-25 12:00:00"
order_date_str_from_db = "2025-11-25 12:00:00"

print("=" * 60)
print("订单信息（使用数据库中的日期）")
print("=" * 60)
print(f"订单ID: {order_id}")
print(f"数据库中的订单日期: {order_date_str_from_db}")
print(f"订单金额: {amount:,.0f}")

# 计算下个付款日期
next_date, date_str, weekday_str = calculate_next_payment_date(order_date_str_from_db)

print("\n" + "=" * 60)
print("下个付款日期")
print("=" * 60)
print(f"日期: {date_str}")
print(f"星期: {weekday_str}")
print(f"计算: 2025-11-25 + 7天 = {next_date.date()}")

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

