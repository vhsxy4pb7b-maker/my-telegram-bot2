"""统计数据相关工具函数"""
import logging
import db_operations
from utils.date_helpers import get_daily_period_date
from constants import DAILY_ALLOWED_PREFIXES

logger = logging.getLogger(__name__)


async def update_liquid_capital(amount: float):
    """更新流动资金（全局余额 + 日结流量）"""
    try:
        await db_operations.update_financial_data('liquid_funds', amount)
        date = get_daily_period_date()
        await db_operations.update_daily_data(date, 'liquid_flow', amount, None)
    except Exception as e:
        logger.error(f"更新流动资金失败: {e}", exc_info=True)
        raise


async def update_all_stats(field: str, amount: float, count: int = 0, group_id: str = None, skip_daily: bool = False):
    """统一更新所有统计数据（全局、日结、分组）

    注意：所有更新操作应该在同一日期下执行，以确保数据一致性。
    如果某个更新失败，前面的更新可能已经成功，需要手动修复或重新计算。
    """
    # 统一获取日期，避免多次调用导致日期不一致
    date = None
    is_daily_field = any(field.startswith(prefix)
                         for prefix in DAILY_ALLOWED_PREFIXES)
    if is_daily_field and not skip_daily:
        date = get_daily_period_date()

    # 提前计算字段名，避免后面使用时未定义
    global_amount_field = field if field.endswith('_amount') or field in [
        'liquid_funds', 'interest'] else f"{field}_amount"
    global_count_field = field if field.endswith('_orders') or field in [
        'new_clients', 'old_clients'] else f"{field}_orders"

    try:
        # 1. 更新全局数据 (financial_data)
        if amount != 0:
            try:
                await db_operations.update_financial_data(global_amount_field, amount)
                logger.debug(f"✅ 已更新全局数据: {global_amount_field} += {amount}")
            except Exception as e:
                logger.error(
                    f"❌ 更新全局数据失败 ({global_amount_field}): {e}", exc_info=True)
                raise

        if count != 0:
            try:
                await db_operations.update_financial_data(global_count_field, float(count))
                logger.debug(f"✅ 已更新全局计数: {global_count_field} += {count}")
            except Exception as e:
                logger.error(
                    f"❌ 更新全局计数失败 ({global_count_field}): {e}", exc_info=True)
                raise

        # 2. 更新日结数据 (daily_data)
        if is_daily_field and not skip_daily and date:
            if amount != 0:
                daily_amount_field = field if field.endswith(
                    '_amount') or field == 'interest' else f"{field}_amount"
                # 更新全局日结
                try:
                    await db_operations.update_daily_data(
                        date, daily_amount_field, amount, None)
                    logger.debug(
                        f"✅ 已更新全局日结: {date} {daily_amount_field} += {amount}")
                except Exception as e:
                    logger.error(
                        f"❌ 更新全局日结失败 ({date}, {daily_amount_field}): {e}", exc_info=True)
                    raise

                # 更新分组日结
                if group_id:
                    try:
                        await db_operations.update_daily_data(
                            date, daily_amount_field, amount, group_id)
                        logger.debug(
                            f"✅ 已更新分组日结: {date} {group_id} {daily_amount_field} += {amount}")
                    except Exception as e:
                        logger.error(
                            f"❌ 更新分组日结失败 ({date}, {group_id}, {daily_amount_field}): {e}", exc_info=True)
                        raise

            if count != 0:
                daily_count_field = field if field.endswith('_orders') or field in [
                    'new_clients', 'old_clients'] else f"{field}_orders"
                # 更新全局日结计数
                try:
                    await db_operations.update_daily_data(
                        date, daily_count_field, count, None)
                    logger.debug(
                        f"✅ 已更新全局日结计数: {date} {daily_count_field} += {count}")
                except Exception as e:
                    logger.error(
                        f"❌ 更新全局日结计数失败 ({date}, {daily_count_field}): {e}", exc_info=True)
                    raise

                # 更新分组日结计数
                if group_id:
                    try:
                        await db_operations.update_daily_data(
                            date, daily_count_field, count, group_id)
                        logger.debug(
                            f"✅ 已更新分组日结计数: {date} {group_id} {daily_count_field} += {count}")
                    except Exception as e:
                        logger.error(
                            f"❌ 更新分组日结计数失败 ({date}, {group_id}, {daily_count_field}): {e}", exc_info=True)
                        raise

        # 3. 更新分组累计数据 (grouped_data)
        if group_id:
            if amount != 0:
                group_amount_field = global_amount_field
                try:
                    await db_operations.update_grouped_data(
                        group_id, group_amount_field, amount)
                    logger.debug(
                        f"✅ 已更新分组累计: {group_id} {group_amount_field} += {amount}")
                except Exception as e:
                    logger.error(
                        f"❌ 更新分组累计失败 ({group_id}, {group_amount_field}): {e}", exc_info=True)
                    raise
            if count != 0:
                group_count_field = global_count_field
                try:
                    await db_operations.update_grouped_data(
                        group_id, group_count_field, float(count))
                    logger.debug(
                        f"✅ 已更新分组累计计数: {group_id} {group_count_field} += {count}")
                except Exception as e:
                    logger.error(
                        f"❌ 更新分组累计计数失败 ({group_id}, {group_count_field}): {e}", exc_info=True)
                    raise

        logger.info(
            f"✅ 统计更新完成: field={field}, amount={amount}, count={count}, group_id={group_id}, date={date}")

    except Exception as e:
        logger.error(
            f"❌ 更新统计数据失败: field={field}, amount={amount}, count={count}, group_id={group_id}, date={date}, error={e}", exc_info=True)
        # 重新抛出异常，让调用者知道更新失败
        # 注意：前面的更新可能已经成功，需要手动修复或重新计算
        raise
