"""订单表格生成工具"""
from typing import List, Dict
import db_operations
from constants import ORDER_STATES


async def format_order_table_row(order: Dict, interests: List[Dict]) -> str:
    """格式化订单表格行"""
    date_str = order.get('date', '')[:10] if order.get('date') else '未知'
    order_id = order.get('order_id', '未知')
    amount = order.get('amount', 0)
    state = ORDER_STATES.get(order.get('state', ''), order.get('state', '未知'))
    
    # 格式化金额
    amount_str = f"{float(amount):,.2f}" if amount else "0.00"
    
    # 构建行
    row = f"{date_str:<12}  {order_id:<15}  {amount_str:>12}  {state:<6}"
    
    # 添加利息记录
    if interests:
        for interest in interests:
            interest_date = interest.get('date', '')[:10] if interest.get('date') else '未知'
            interest_amount = interest.get('amount', 0)
            interest_str = f"{float(interest_amount):,.2f}" if interest_amount else "0.00"
            row += f"\n{'':<12}  {'利息: ' + interest_date:<15}  {interest_str:>12}"
    
    return row


async def generate_order_table(orders: List[Dict], daily_interest: float = 0) -> str:
    """生成订单总表"""
    if not orders:
        return "订单总表（有效订单）\n═══════════════════════════════════════\n\n暂无有效订单"
    
    table = "订单总表（有效订单）\n"
    table += "═══════════════════════════════════════\n"
    table += f"{'时间':<12}  {'订单号':<15}  {'金额':>12}  {'状态':<6}\n"
    table += "─────────────────────────────────────────\n"
    
    for order in orders:
        order_id = order.get('order_id')
        # 获取该订单的所有利息记录
        if order_id:
            interests = await db_operations.get_all_interest_by_order_id(order_id)
        else:
            interests = []
        row = await format_order_table_row(order, interests)
        table += row + "\n"
    
    table += "═══════════════════════════════════════\n"
    if daily_interest > 0:
        table += f"当日利息汇总: {daily_interest:,.2f}\n"
    
    return table


async def _generate_orders_summary_table(orders: List[Dict], title: str) -> str:
    """生成订单汇总表格（通用函数）"""
    if not orders:
        return ""
    
    table = f"\n{title}\n"
    table += "═══════════════════════════════════════\n"
    table += f"{'时间':<12}  {'订单号':<15}  {'金额':>12}  {'完成时间':<20}\n"
    table += "─────────────────────────────────────────\n"
    
    for order in orders:
        date_str = order.get('date', '')[:10] if order.get('date') else '未知'
        order_id = order.get('order_id', '未知')
        amount = order.get('amount', 0)
        updated_at = order.get('updated_at', '')[:19] if order.get('updated_at') else '未知'
        amount_str = f"{float(amount):,.2f}" if amount else "0.00"
        
        table += f"{date_str:<12}  {order_id:<15}  {amount_str:>12}  {updated_at:<20}\n"
    
    table += "═══════════════════════════════════════\n"
    
    return table


async def generate_completed_orders_table(orders: List[Dict]) -> str:
    """生成已完成订单表格"""
    return await _generate_orders_summary_table(orders, "已完成订单（当日）")


async def generate_breach_end_orders_table(orders: List[Dict]) -> str:
    """生成违约完成订单表格（仅当日有变动的）"""
    return await _generate_orders_summary_table(orders, "违约完成订单（当日有变动）")

