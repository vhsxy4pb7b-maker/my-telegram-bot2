"""日切报表生成器"""
import logging
from typing import Dict
import db_operations
from utils.order_table_helpers import (
    generate_order_table,
    generate_completed_orders_table,
    generate_breach_end_orders_table
)

logger = logging.getLogger(__name__)


async def calculate_daily_summary(date: str) -> Dict:
    """计算指定日期的日切数据"""
    try:
        # 获取新增订单
        new_orders = await db_operations.get_new_orders_by_date(date)
        new_orders_count = len(new_orders)
        new_orders_amount = sum(order.get('amount', 0) or 0 for order in new_orders)
        
        # 获取完成的订单
        completed_orders = await db_operations.get_completed_orders_by_date(date)
        completed_orders_count = len(completed_orders)
        completed_orders_amount = sum(order.get('amount', 0) or 0 for order in completed_orders)
        
        # 获取违约完成的订单（仅当日有变动的）
        breach_end_orders = await db_operations.get_breach_end_orders_by_date(date)
        breach_end_orders_count = len(breach_end_orders)
        breach_end_orders_amount = sum(order.get('amount', 0) or 0 for order in breach_end_orders)
        
        # 获取当日利息收入
        daily_interest = await db_operations.get_daily_interest_total(date)
        
        # 获取当日开销
        expenses = await db_operations.get_daily_expenses(date)
        company_expenses = expenses.get('company_expenses', 0.0)
        other_expenses = expenses.get('other_expenses', 0.0)
        
        return {
            'new_orders_count': new_orders_count,
            'new_orders_amount': new_orders_amount,
            'completed_orders_count': completed_orders_count,
            'completed_orders_amount': completed_orders_amount,
            'breach_end_orders_count': breach_end_orders_count,
            'breach_end_orders_amount': breach_end_orders_amount,
            'daily_interest': daily_interest,
            'company_expenses': company_expenses,
            'other_expenses': other_expenses
        }
    except Exception as e:
        logger.error(f"计算日切数据失败: {e}", exc_info=True)
        return {
            'new_orders_count': 0,
            'new_orders_amount': 0.0,
            'completed_orders_count': 0,
            'completed_orders_amount': 0.0,
            'breach_end_orders_count': 0,
            'breach_end_orders_amount': 0.0,
            'daily_interest': 0.0,
            'company_expenses': 0.0,
            'other_expenses': 0.0
        }


async def generate_daily_report(date: str) -> str:
    """生成日切报表"""
    try:
        # 计算日切数据
        summary = await calculate_daily_summary(date)
        
        # 保存日切数据
        await db_operations.save_daily_summary(date, summary)
        
        # 生成报表文本
        report = f"📊 日切报表 ({date})\n"
        report += "═══════════════════════════════════════\n\n"
        
        # 订单总表
        valid_orders = await db_operations.get_all_valid_orders()
        daily_interest = summary.get('daily_interest', 0.0)
        order_table = await generate_order_table(valid_orders, daily_interest)
        report += order_table + "\n\n"
        
        # 日切数据表
        report += "日切数据汇总\n"
        report += "═══════════════════════════════════════\n"
        report += f"新增订单: {summary.get('new_orders_count', 0)} 个, "
        report += f"金额: {summary.get('new_orders_amount', 0.0):,.2f}\n"
        report += f"完结订单: {summary.get('completed_orders_count', 0)} 个, "
        report += f"金额: {summary.get('completed_orders_amount', 0.0):,.2f}\n"
        report += f"违约完成: {summary.get('breach_end_orders_count', 0)} 个, "
        report += f"金额: {summary.get('breach_end_orders_amount', 0.0):,.2f}\n"
        report += f"当日利息: {summary.get('daily_interest', 0.0):,.2f}\n"
        report += f"公司开销: {summary.get('company_expenses', 0.0):,.2f}\n"
        report += f"其他开销: {summary.get('other_expenses', 0.0):,.2f}\n"
        report += f"总开销: {summary.get('company_expenses', 0.0) + summary.get('other_expenses', 0.0):,.2f}\n"
        report += "═══════════════════════════════════════\n\n"
        
        # 已完成订单列表
        completed_orders = await db_operations.get_completed_orders_by_date(date)
        if completed_orders:
            completed_table = await generate_completed_orders_table(completed_orders)
            report += completed_table + "\n"
        
        # 违约完成订单列表
        breach_end_orders = await db_operations.get_breach_end_orders_by_date(date)
        if breach_end_orders:
            breach_table = await generate_breach_end_orders_table(breach_end_orders)
            report += breach_table + "\n"
        
        return report
    except Exception as e:
        logger.error(f"生成日切报表失败: {e}", exc_info=True)
        return f"❌ 生成日切报表失败: {e}"

