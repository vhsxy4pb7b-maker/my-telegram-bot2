"""播报相关工具函数"""
from datetime import datetime, timedelta, date
from typing import Tuple, Optional


def calculate_next_payment_date(order_date: Optional[date] = None) -> Tuple[datetime, str, str]:
    """
    计算下一个付款日期（从当前日期找到下一个与订单日期相同星期几的日期）
    
    Args:
        order_date: 订单日期（可选，如果为None则使用当前日期）
    
    返回: (日期对象, 日期字符串, 星期字符串)
    
    逻辑：
    - 订单的付款日期是固定的星期几（由订单日期决定）
    - 从当前日期开始，找到下一个与订单日期相同星期几的日期
    - 如果当前日期就是订单的付款星期几，那么下个付款日期是7天后
    
    示例：
    - 订单日期：2025-07-22 (周二)
    - 当前日期：2025-11-29 (周五)
    - 下个付款日期：2025-12-03 (下一个周二)
    
    - 订单日期：2025-11-25 (周二)
    - 当前日期：2025-11-29 (周五)
    - 下个付款日期：2025-12-02 (下一个周二)
    """
    # 获取当前日期
    today = datetime.now().date()
    
    # 如果提供了订单日期，获取订单日期的星期几
    if order_date:
        if isinstance(order_date, str):
            # 如果是字符串，解析为日期
            try:
                # 尝试解析 "YYYY-MM-DD HH:MM:SS" 或 "YYYY-MM-DD"
                if ' ' in order_date:
                    order_date = datetime.strptime(order_date.split()[0], "%Y-%m-%d").date()
                else:
                    order_date = datetime.strptime(order_date, "%Y-%m-%d").date()
            except ValueError:
                # 解析失败，使用当前日期
                order_date = today
        # 获取订单日期的星期几（0=Monday, 1=Tuesday, ..., 6=Sunday）
        target_weekday = order_date.weekday()
    else:
        # 如果没有提供订单日期，使用当前日期的星期几
        target_weekday = today.weekday()
        order_date = today
    
    # 计算从今天到下个目标星期几的天数
    days_until_target = (target_weekday - today.weekday()) % 7
    
    # 如果今天是目标星期几，那么下个付款日期是7天后
    if days_until_target == 0:
        days_until_target = 7
    
    # 计算下个付款日期
    next_payment_date = today + timedelta(days=days_until_target)
    
    # 转换为 datetime 对象（用于返回）
    next_payment_datetime = datetime.combine(next_payment_date, datetime.min.time())
    
    # 格式化日期（格式：November 26,2025）
    date_str = next_payment_date.strftime("%B %d,%Y")
    weekday_str = next_payment_date.strftime("%A")
    
    return next_payment_datetime, date_str, weekday_str


def format_broadcast_message(
    principal: float,
    principal_12: float,
    outstanding_interest: float = 0,
    date_str: str = None,
    weekday_str: str = None
) -> str:
    """
    生成播报消息模板
    
    Args:
        principal: 本金金额
        principal_12: 本金12%金额
        outstanding_interest: 未付利息（默认0）
        date_str: 日期字符串（如果为None，自动计算）
        weekday_str: 星期字符串（如果为None，自动计算）
    
    Returns:
        格式化后的播报消息
    """
    # 如果没有提供日期，自动计算
    if date_str is None or weekday_str is None:
        _, date_str, weekday_str = calculate_next_payment_date()
    
    # 格式化金额（添加千位分隔符）
    principal_formatted = f"{principal:,.0f}"
    principal_12_formatted = f"{principal_12:,.0f}"
    
    # 构建播报消息
    message = (
        f"Your next payment is due on {date_str} ({weekday_str}) "
        f"for {principal_formatted} or {principal_12_formatted} to defer the principal payment for one week.\n\n"
        f"Your outstanding interest is {outstanding_interest}"
    )
    
    return message

