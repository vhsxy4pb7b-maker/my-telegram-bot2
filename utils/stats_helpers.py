"""统计数据相关工具函数"""
import db_operations
from utils.date_helpers import get_daily_period_date
from constants import DAILY_ALLOWED_PREFIXES


async def update_liquid_capital(amount: float):
    """更新流动资金（全局余额 + 日结流量）"""
    await db_operations.update_financial_data('liquid_funds', amount)
    date = get_daily_period_date()
    await db_operations.update_daily_data(date, 'liquid_flow', amount, None)


async def update_all_stats(field: str, amount: float, count: int = 0, group_id: str = None):
    """统一更新所有统计数据（全局、日结、分组）"""
    if amount != 0:
        global_amount_field = field if field.endswith('_amount') or field in [
            'liquid_funds', 'interest'] else f"{field}_amount"
        await db_operations.update_financial_data(global_amount_field, amount)

    if count != 0:
        global_count_field = field if field.endswith('_orders') or field in [
            'new_clients', 'old_clients'] else f"{field}_orders"
        await db_operations.update_financial_data(global_count_field, count)

    is_daily_field = any(field.startswith(prefix)
                         for prefix in DAILY_ALLOWED_PREFIXES)

    if is_daily_field:
        date = get_daily_period_date()
        if amount != 0:
            daily_amount_field = field if field.endswith(
                '_amount') or field == 'interest' else f"{field}_amount"
            await db_operations.update_daily_data(
                date, daily_amount_field, amount, None)
        if count != 0:
            daily_count_field = field if field.endswith('_orders') or field in [
                'new_clients', 'old_clients'] else f"{field}_orders"
            await db_operations.update_daily_data(
                date, daily_count_field, count, None)

        if group_id:
            if amount != 0:
                await db_operations.update_daily_data(
                    date, daily_amount_field, amount, group_id)
            if count != 0:
                await db_operations.update_daily_data(
                    date, daily_count_field, count, group_id)

    if group_id:
        if amount != 0:
            group_amount_field = global_amount_field
            await db_operations.update_grouped_data(
                group_id, group_amount_field, amount)
        if count != 0:
            group_count_field = global_count_field
            await db_operations.update_grouped_data(
                group_id, group_count_field, count)
