"""测试播报功能 - 订单 2506060110"""
from datetime import datetime, date
from utils.broadcast_helpers import calculate_next_payment_date, format_broadcast_message

# 订单ID: 2506060110 (标准10位格式)
order_id = '2506060110'

print("=" * 60)
print("订单信息")
print("=" * 60)
print(f"订单ID: {order_id}")
print(f"订单ID长度: {len(order_id)}")

# 解析订单信息（标准格式：YYMMDDNNKK）
if len(order_id) == 10:
    date_part = order_id[:6]  # YYMMDD = 250606
    seq_part = order_id[6:8]  # NN = 01
    amount_part = int(order_id[8:10])  # KK = 10
    amount = amount_part * 1000  # 10,000
    
    print(f"格式: 标准10位格式 (YYMMDDNNKK)")
    print(f"日期部分: {date_part}")
    print(f"序号部分: {seq_part}")
    print(f"金额部分: {amount_part}")
    
    # 解析日期
    try:
        full_date_str = f'20{date_part}'  # 20250606
        order_date_from_id = datetime.strptime(full_date_str, '%Y%m%d').date()
        print(f"解析的订单日期: {order_date_from_id} ({order_date_from_id.strftime('%A')})")
        print(f"订单金额: {amount:,.0f}")
    except ValueError as e:
        print(f"日期解析失败: {e}")
        order_date_from_id = None
        amount = 0
else:
    print(f"错误: 订单ID长度不符合标准格式（应该是10位）")
    order_date_from_id = None
    amount = 0

if order_date_from_id:
    # 计算下个付款日期
    next_date, date_str, weekday_str = calculate_next_payment_date(order_date_from_id)
    
    print("\n" + "=" * 60)
    print("下个付款日期")
    print("=" * 60)
    print(f"订单日期: {order_date_from_id} ({order_date_from_id.strftime('%A')})")
    print(f"当前日期: {datetime.now().date()} ({datetime.now().strftime('%A')})")
    print(f"下个付款日期: {date_str} ({weekday_str})")
    print(f"计算逻辑: 从当前日期找到下一个与订单日期相同星期几的日期")
    
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

print("\n" + "=" * 60)
print("注意")
print("=" * 60)
print("实际播报功能使用数据库中的订单日期字段")
print("如果数据库中的订单日期与订单ID解析的日期不同，")
print("播报功能会使用数据库中的日期来计算下个付款日期。")

