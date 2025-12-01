"""订单操作回调处理器"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.order_handlers import (
    set_normal, set_overdue, set_end, set_breach, set_breach_end
)
from handlers.command_handlers import show_current_order
import db_operations
from handlers.attribution_handlers import change_orders_attribution
from utils.chat_helpers import is_group_chat


async def handle_order_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理订单操作的回调"""
    query = update.callback_query
    if not query:
        return

    # 获取原始数据
    data = query.data
    if not data:
        return

    # 处理更改归属的回调
    if data == "order_action_change_attribution":
        # 获取当前订单
        chat_id = query.message.chat_id
        order = await db_operations.get_order_by_chat_id(chat_id)
        if not order:
            is_group = is_group_chat(update)
            msg = "❌ Order not found" if is_group else "❌ 没有找到订单"
            await query.answer(msg, show_alert=True)
            return

        # 获取所有归属ID列表
        all_group_ids = await db_operations.get_all_group_ids()
        if not all_group_ids:
            is_group = is_group_chat(update)
            msg = "❌ No available Group ID" if is_group else "❌ 没有可用的归属ID"
            await query.answer(msg, show_alert=True)
            return

        # 显示归属ID选择界面
        is_group = is_group_chat(update)
        keyboard = []
        row = []
        for gid in sorted(all_group_ids):
            # 当前归属ID显示为选中状态
            if gid == order['group_id']:
                row.append(InlineKeyboardButton(
                    f"✓ {gid}", callback_data=f"order_change_to_{gid}"))
            else:
                row.append(InlineKeyboardButton(
                    gid, callback_data=f"order_change_to_{gid}"))
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        back_text = "🔙 Back" if is_group else "🔙 返回"
        keyboard.append([InlineKeyboardButton(
            back_text, callback_data="order_action_back")])

        if is_group:
            msg_text = (
                f"🔄 Change Attribution\n\n"
                f"Current: {order['group_id']}\n"
                f"Order ID: {order['order_id']}\n"
                f"Amount: {order['amount']:.2f}\n\n"
                f"Select new Group ID:"
            )
        else:
            msg_text = (
                f"🔄 更改归属\n\n"
                f"当前归属: {order['group_id']}\n"
                f"订单ID: {order['order_id']}\n"
                f"金额: {order['amount']:.2f}\n\n"
                f"请选择新的归属ID:"
            )

        await query.edit_message_text(
            msg_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await query.answer()
        return

    # 处理选择归属ID的回调
    if data.startswith("order_change_to_"):
        new_group_id = data[16:]  # 提取新的归属ID

        # 获取当前订单
        chat_id = query.message.chat_id
        order = await db_operations.get_order_by_chat_id(chat_id)
        is_group = is_group_chat(update)

        if not order:
            msg = "❌ Order not found" if is_group else "❌ 没有找到订单"
            await query.answer(msg, show_alert=True)
            return

        # 如果归属ID相同，无需更改
        if order['group_id'] == new_group_id:
            msg = "✅ Group ID unchanged" if is_group else "✅ 归属ID未变更"
            await query.answer(msg, show_alert=True)
            return

        # 执行归属变更（单个订单）
        orders = [order]
        success_count, fail_count = await change_orders_attribution(
            update, context, orders, new_group_id
        )

        if success_count > 0:
            msg = "✅ Attribution changed" if is_group else "✅ 归属变更完成"
            await query.answer(msg)
            # 在群聊中不刷新订单信息显示，只保留结果消息
            # 在私聊中可以刷新显示
            if not is_group:
                await show_current_order(update, context)
        else:
            msg = "❌ Attribution change failed" if is_group else "❌ 归属变更失败"
            await query.answer(msg, show_alert=True)
        return

    # 处理返回按钮
    if data == "order_action_back":
        is_group = is_group_chat(update)
        # 在群聊中，返回时不刷新显示，只关闭当前选择界面
        if is_group:
            await query.delete_message()
        else:
            await show_current_order(update, context)
        await query.answer()
        return

    # 处理其他操作
    action = data.replace("order_action_", "")

    if action == "normal":
        await set_normal(update, context)
    elif action == "overdue":
        await set_overdue(update, context)
    elif action == "end":
        await set_end(update, context)
    elif action == "breach":
        await set_breach(update, context)
    elif action == "breach_end":
        await set_breach_end(update, context)
    elif action == "create":
        # create 命令需要参数，这里只能提示用法
        await query.message.reply_text("To create an order, please use command: /create <Group ID> <Customer A/B> <Amount>")

    # 尝试 answer callback，消除加载状态
    try:
        await query.answer()
    except:
        pass
