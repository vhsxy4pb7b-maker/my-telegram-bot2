"""测试播报功能"""
from datetime import datetime, date
from utils.broadcast_helpers import calculate_next_payment_date, format_broadcast_message

# 解析订单ID: 2505200104
order_id = '2505200104'

# 解析订单信息
date_part = order_id[:6]  # 250520
amount_part = int(order_id[8:10])  # 04
amount = amount_part * 1000  # 4000

# 解析日期
full_date_str = f'20{date_part}'  # 20250520
order_date = datetime.strptime(full_date_str, '%Y%m%d').date()

print("=" * 60)
print("订单信息")
print("=" * 60)
print(f"订单ID: {order_id}")
print(f"订单日期: {order_date} ({order_date.strftime('%A')})")
print(f"订单金额: {amount:,.0f}")

# 计算下个付款日期
next_date, date_str, weekday_str = calculate_next_payment_date(order_date)

print("\n" + "=" * 60)
print("下个付款日期")
print("=" * 60)
print(f"日期: {date_str}")
print(f"星期: {weekday_str}")
print(f"计算: {order_date} + 7天 = {next_date.date()}")

# 计算金额
principal = amount
principal_12 = principal * 0.12
outstanding_interest = 0

# 生成播报消息
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

