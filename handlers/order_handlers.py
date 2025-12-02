"""订单状态处理相关命令"""
import logging
from telegram import Update
from telegram.ext import ContextTypes
import db_operations
from utils.chat_helpers import is_group_chat
from utils.stats_helpers import update_all_stats, update_liquid_capital
from utils.date_helpers import get_daily_period_date
from decorators import authorized_required, group_chat_only

logger = logging.getLogger(__name__)


def _get_chat_info(update: Update):
    """从update中提取chat_id和reply_func"""
    if update.message:
        return update.message.chat_id, update.message.reply_text
    elif update.callback_query:
        return update.callback_query.message.chat_id, update.callback_query.message.reply_text
    return None, None


@authorized_required
@group_chat_only
async def set_normal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """转为正常状态"""
    try:
        chat_id, reply_func = _get_chat_info(update)
        if not chat_id or not reply_func:
            return

        order = await db_operations.get_order_by_chat_id(chat_id)
        if not order:
            message = "❌ Failed: No active order."
            await reply_func(message)
            return

        if order['state'] != 'overdue':
            message = "❌ Failed: Order must be overdue."
            await reply_func(message)
            return

        old_state = order['state']
        if not await db_operations.update_order_state(chat_id, 'normal'):
            message = "❌ Failed: DB Error"
            await reply_func(message)
            return

        # 记录操作历史（用于撤销）
        user_id = update.effective_user.id if update.effective_user else None
        if user_id:
            from handlers.undo_handlers import reset_undo_count
            await db_operations.record_operation(
                user_id=user_id,
                operation_type='order_state_change',
                operation_data={
                    'chat_id': chat_id,
                    'order_id': order['order_id'],
                    'old_state': old_state,
                    'new_state': 'normal',
                    'group_id': order['group_id'],
                    'amount': order['amount']
                },
                chat_id=chat_id
            )
            if context:
                reset_undo_count(context, user_id)

        if is_group_chat(update):
            await reply_func(f"✅ Status Updated: normal\nOrder ID: {order['order_id']}")
        else:
            await reply_func(
                f"✅ Status Updated: normal\n"
                f"Order ID: {order['order_id']}\n"
                f"State: normal"
            )
    except Exception as e:
        logger.error(f"更新订单状态时出错: {e}", exc_info=True)
        message = "❌ Error processing request."
        if update.message:
            await update.message.reply_text(message)
        elif update.callback_query:
            await update.callback_query.message.reply_text(message)


@authorized_required
@group_chat_only
async def set_overdue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """转为逾期状态"""
    try:
        chat_id, reply_func = _get_chat_info(update)
        if not chat_id or not reply_func:
            return

        order = await db_operations.get_order_by_chat_id(chat_id)
        if not order:
            message = "❌ Failed: No active order."
            await reply_func(message)
            return

        if order['state'] != 'normal':
            message = "❌ Failed: Order must be normal."
            await reply_func(message)
            return

        old_state = order['state']
        if not await db_operations.update_order_state(chat_id, 'overdue'):
            message = "❌ Failed: DB Error"
            await reply_func(message)
            return

        # 记录操作历史（用于撤销）
        user_id = update.effective_user.id if update.effective_user else None
        if user_id:
            from handlers.undo_handlers import reset_undo_count
            await db_operations.record_operation(
                user_id=user_id,
                operation_type='order_state_change',
                operation_data={
                    'chat_id': chat_id,
                    'order_id': order['order_id'],
                    'old_state': old_state,
                    'new_state': 'overdue',
                    'group_id': order['group_id'],
                    'amount': order['amount']
                },
                chat_id=chat_id
            )
            if context:
                reset_undo_count(context, user_id)

        if is_group_chat(update):
            await reply_func(f"✅ Status Updated: overdue\nOrder ID: {order['order_id']}")
        else:
            await reply_func(
                f"✅ Status Updated: overdue\n"
                f"Order ID: {order['order_id']}\n"
                f"State: overdue"
            )
    except Exception as e:
        logger.error(f"更新订单状态时出错: {e}", exc_info=True)
        message = "❌ Error processing request."
        if update.message:
            await update.message.reply_text(message)
        elif update.callback_query:
            await update.callback_query.message.reply_text(message)


@authorized_required
@group_chat_only
async def set_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """标记订单为完成"""
    chat_id, reply_func = _get_chat_info(update)
    if not chat_id or not reply_func:
        return

    order = await db_operations.get_order_by_chat_id(chat_id)
    if not order:
        message = "❌ Failed: No active order."
        await reply_func(message)
        return

    if order['state'] not in ('normal', 'overdue'):
        message = "❌ Failed: State must be normal or overdue."
        await reply_func(message)
        return

    old_state = order['state']
    await db_operations.update_order_state(chat_id, 'end')
    group_id = order['group_id']
    amount = order['amount']

    # 统一获取日期，确保统计更新和收入记录使用相同的日期
    date = get_daily_period_date()

    try:
        await update_all_stats('valid', -amount, -1, group_id)
        await update_all_stats('completed', amount, 1, group_id)
        await update_liquid_capital(amount)

        # 记录收入明细（使用相同的日期）
        user_id = update.effective_user.id if update.effective_user else None
        try:
            await db_operations.record_income(
                date=date,
                type='completed',
                amount=amount,
                group_id=group_id,
                order_id=order['order_id'],
                order_date=order['date'],
                customer=order['customer'],
                weekday_group=order['weekday_group'],
                note="订单完成",
                created_by=user_id
            )
        except Exception as e:
            logger.error(f"记录订单完成收入明细失败: {e}", exc_info=True)
            # 继续执行，不中断流程
    except Exception as e:
        logger.error(f"更新订单完成统计数据失败: {e}", exc_info=True)
        # 重新抛出异常，让用户知道操作失败
        message = f"❌ 更新统计失败，请稍后重试或联系管理员。错误: {str(e)}"
        await reply_func(message)
        return

    # 记录操作历史（用于撤销）
    if user_id:
        from handlers.undo_handlers import reset_undo_count
        await db_operations.record_operation(
            user_id=user_id,
            operation_type='order_completed',
            operation_data={
                'chat_id': chat_id,
                'order_id': order['order_id'],
                'group_id': group_id,
                'amount': amount,
                'old_state': old_state,
                'date': get_daily_period_date()
            },
            chat_id=chat_id
        )
        if context:
            reset_undo_count(context, user_id)

    if is_group_chat(update):
        await reply_func(f"✅ Order Completed\nAmount: {amount:.2f}")
    else:
        await reply_func(
            f"✅ Order Completed!\n"
            f"Order ID: {order['order_id']}\n"
            f"Amount: {amount:.2f}"
        )


@authorized_required
@group_chat_only
async def set_breach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """标记为违约"""
    try:
        chat_id, reply_func = _get_chat_info(update)
        if not chat_id or not reply_func:
            return

        order = await db_operations.get_order_by_chat_id(chat_id)
        if not order:
            message = "❌ Failed: No active order."
            await reply_func(message)
            return

        # 允许从 normal 或 overdue 变更为 breach
        if order['state'] not in ['normal', 'overdue']:
            message = "❌ Failed: Order must be normal or overdue."
            await reply_func(message)
            return

        old_state = order['state']
        if not await db_operations.update_order_state(chat_id, 'breach'):
            message = "❌ Failed: DB Error"
            await reply_func(message)
            return

        group_id = order['group_id']
        amount = order['amount']

        await update_all_stats('valid', -amount, -1, group_id)
        await update_all_stats('breach', amount, 1, group_id)

        # 记录操作历史（用于撤销）
        user_id = update.effective_user.id if update.effective_user else None
        if user_id:
            from handlers.undo_handlers import reset_undo_count
            await db_operations.record_operation(
                user_id=user_id,
                operation_type='order_state_change',
                operation_data={
                    'chat_id': chat_id,
                    'order_id': order['order_id'],
                    'old_state': old_state,
                    'new_state': 'breach',
                    'group_id': group_id,
                    'amount': amount
                },
                chat_id=chat_id
            )
            if context:
                reset_undo_count(context, user_id)

        if is_group_chat(update):
            await reply_func(f"✅ Marked as Breach\nAmount: {amount:.2f}")
        else:
            await reply_func(
                f"✅ Order Marked as Breach!\n"
                f"Order ID: {order['order_id']}\n"
                f"Amount: {amount:.2f}"
            )
    except Exception as e:
        logger.error(f"更新订单状态时出错: {e}", exc_info=True)
        message = "❌ Error processing request."
        if update.message:
            await update.message.reply_text(message)
        elif update.callback_query:
            await update.callback_query.message.reply_text(message)


@authorized_required
@group_chat_only
async def set_breach_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """违约订单完成 - 请求金额"""
    chat_id, reply_func = _get_chat_info(update)
    if not chat_id or not reply_func:
        return

    args = context.args if update.message else None

    order = await db_operations.get_order_by_chat_id(chat_id)
    if not order:
        message = "❌ Failed: No active order."
        await reply_func(message)
        return

    if order['state'] != 'breach':
        message = "❌ Failed: Order must be in breach."
        await reply_func(message)
        return

    if args and len(args) > 0:
        try:
            amount = float(args[0])
            if amount <= 0:
                await reply_func("❌ Amount must be positive.")
                return

            await db_operations.update_order_state(chat_id, 'breach_end')
            group_id = order['group_id']

            # 统一获取日期，确保统计更新和收入记录使用相同的日期
            date = get_daily_period_date()

            try:
                await update_all_stats('breach_end', amount, 1, group_id)
                await update_liquid_capital(amount)

                # 记录收入明细（使用相同的日期）
                user_id = update.effective_user.id if update.effective_user else None
                try:
                    await db_operations.record_income(
                        date=date,
                        type='breach_end',
                        amount=amount,
                        group_id=group_id,
                        order_id=order['order_id'],
                        order_date=order['date'],
                        customer=order['customer'],
                        weekday_group=order['weekday_group'],
                        note="违约完成",
                        created_by=user_id
                    )
                except Exception as e:
                    logger.error(f"记录违约完成收入明细失败: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"更新违约完成统计数据失败: {e}", exc_info=True)
                await reply_func(f"❌ 更新统计失败，请稍后重试或联系管理员。错误: {str(e)}")
                return

            # 记录操作历史（用于撤销）
            if user_id:
                from handlers.undo_handlers import reset_undo_count
                await db_operations.record_operation(
                    user_id=user_id,
                    operation_type='order_breach_end',
                    operation_data={
                        'chat_id': chat_id,
                        'order_id': order['order_id'],
                        'group_id': group_id,
                        'amount': amount,
                        'date': get_daily_period_date()
                    },
                    chat_id=chat_id
                )
                reset_undo_count(context, user_id)

            msg_en = f"✅ Breach Order Ended\nAmount: {amount:.2f}"

            if is_group_chat(update):
                await reply_func(msg_en)
            else:
                await reply_func(msg_en + f"\nOrder ID: {order['order_id']}")
            return

        except ValueError:
            await reply_func("❌ Invalid amount format.")
            return

    if is_group_chat(update):
        prompt_msg = await reply_func(
            "Please enter the final amount for this breach order (e.g., 5000).\n"
            "This amount will be recorded as liquid capital inflow."
        )
        # 保存提示消息的ID，以便后续删除
        if prompt_msg:
            context.user_data['breach_end_prompt_msg_id'] = prompt_msg.message_id
    else:
        await reply_func("Please enter the final amount for breach order:")

    context.user_data['state'] = 'WAITING_BREACH_END_AMOUNT'
    context.user_data['breach_end_chat_id'] = chat_id
