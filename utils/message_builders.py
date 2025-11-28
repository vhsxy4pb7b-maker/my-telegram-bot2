"""消息构建工具函数"""
from typing import Optional


def build_order_creation_message(
    order_id: str,
    group_id: str,
    created_at: str,
    weekday_group: Optional[str],
    customer: str,
    amount: float,
    initial_state: str,
    is_historical: bool = False
) -> str:
    """
    构建订单创建成功消息
    
    Args:
        order_id: 订单ID
        group_id: 归属ID
        created_at: 创建时间
        weekday_group: 星期分组（可选）
        customer: 客户类型 ('A' 或 'B')
        amount: 订单金额
        initial_state: 初始状态
        is_historical: 是否为历史订单
    
    Returns:
        格式化后的消息字符串
    """
    if is_historical:
        title = "✅ Historical Order Imported"
        customer_suffix = " (Historical)"
        footer = "\n⚠️ Funds Update: Skipped (Historical Data Only)\n📢 Broadcast: Skipped (Historical Data Only)"
    else:
        title = "✅ Order Created Successfully"
        customer_suffix = ""
        footer = ""
    
    customer_name = 'New' if customer == 'A' else 'Returning'
    
    message = (
        f"{title}\n\n"
        f"📋 Order ID: {order_id}\n"
        f"🏷️ Group ID: {group_id}\n"
        f"📅 Date: {created_at}\n"
    )
    
    if weekday_group and not is_historical:
        message += f"👥 Week Group: {weekday_group}\n"
    
    message += (
        f"👤 Customer: {customer_name}{customer_suffix}\n"
        f"💰 Amount: {amount:.2f}\n"
        f"📈 Status: {initial_state}"
        f"{footer}"
    )
    
    return message

