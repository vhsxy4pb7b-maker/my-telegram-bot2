"""聊天相关工具函数"""
from telegram import Update
from constants import WEEKDAY_GROUP
from datetime import date


def is_group_chat(update: Update) -> bool:
    """判断是否是群组聊天"""
    return update.effective_chat.type in ['group', 'supergroup']


def get_current_group():
    """获取当前星期对应的分组"""
    today = date.today().weekday()
    return WEEKDAY_GROUP[today]


def get_weekday_group_from_date(order_date: date) -> str:
    """根据订单日期获取星期分组"""
    weekday = order_date.weekday()  # 0=Monday, 1=Tuesday, ..., 6=Sunday
    return WEEKDAY_GROUP[weekday]


def reply_in_group(update: Update, message: str):
    """在群组中回复消息"""
    if is_group_chat(update):
        return update.message.reply_text(message)
    else:
        # 私聊保持中文
        return update.message.reply_text(message)
