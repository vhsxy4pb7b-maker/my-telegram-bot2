"""定时播报执行器"""
import logging
import asyncio
from datetime import datetime, time as dt_time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import db_operations

logger = logging.getLogger(__name__)

# 全局调度器
scheduler = None


async def send_scheduled_broadcast(bot, broadcast):
    """发送定时播报"""
    try:
        chat_id = broadcast['chat_id']
        message = broadcast['message']
        
        if not chat_id:
            logger.warning(f"播报 {broadcast['slot']} 没有设置chat_id，跳过发送")
            return
        
        await bot.send_message(chat_id=chat_id, text=message)
        logger.info(f"定时播报 {broadcast['slot']} 已发送到群组 {chat_id}")
    except Exception as e:
        logger.error(f"发送定时播报 {broadcast['slot']} 失败: {e}", exc_info=True)


async def setup_scheduled_broadcasts(bot):
    """设置定时播报任务"""
    global scheduler
    
    if scheduler is None:
        scheduler = AsyncIOScheduler()
        scheduler.start()
    
    # 清除所有现有任务
    scheduler.remove_all_jobs()
    
    # 获取所有激活的定时播报
    broadcasts = await db_operations.get_active_scheduled_broadcasts()
    
    for broadcast in broadcasts:
        try:
            time_str = broadcast['time']
            # 解析时间 (HH:MM 或 HH)
            time_parts = time_str.split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            
            # 创建定时任务（每天执行）
            job_id = f"broadcast_{broadcast['slot']}"
            
            scheduler.add_job(
                send_scheduled_broadcast,
                trigger=CronTrigger(hour=hour, minute=minute),
                args=[bot, broadcast],
                id=job_id,
                replace_existing=True
            )
            
            logger.info(f"已设置定时播报 {broadcast['slot']}: 每天 {time_str} 发送到群组 {broadcast['chat_id']}")
        except Exception as e:
            logger.error(f"设置定时播报 {broadcast['slot']} 失败: {e}", exc_info=True)


async def reload_scheduled_broadcasts(bot):
    """重新加载定时播报任务"""
    await setup_scheduled_broadcasts(bot)


async def send_daily_report(bot):
    """发送日切报表给所有管理员"""
    try:
        from utils.daily_report_generator import generate_daily_report
        from utils.date_helpers import get_daily_period_date
        from config import ADMIN_IDS
        
        # 获取日切日期（使用get_daily_period_date，因为日切是在23:00后）
        # 如果当前时间在23:00之后，get_daily_period_date会返回明天的日期
        # 但我们需要统计的是今天的数据，所以需要减一天
        from datetime import datetime, timedelta
        import pytz
        tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(tz)
        # 如果当前时间在23:00之后，统计今天的数据；否则统计昨天的数据
        if now.hour >= 23:
            # 23:00之后，统计今天的数据
            report_date = now.strftime("%Y-%m-%d")
        else:
            # 23:00之前，统计昨天的数据
            yesterday = now - timedelta(days=1)
            report_date = yesterday.strftime("%Y-%m-%d")
        
        # 生成日切报表
        report = await generate_daily_report(report_date)
        
        # 发送给所有管理员
        success_count = 0
        fail_count = 0
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(chat_id=admin_id, text=report)
                success_count += 1
                logger.info(f"日切报表已发送给管理员 {admin_id}")
            except Exception as e:
                fail_count += 1
                logger.error(f"发送日切报表给管理员 {admin_id} 失败: {e}", exc_info=True)
        
        logger.info(f"日切报表发送完成: 成功 {success_count}, 失败 {fail_count}")
    except Exception as e:
        logger.error(f"发送日切报表失败: {e}", exc_info=True)


async def setup_daily_report(bot):
    """设置日切报表自动发送任务（每天23:05执行）"""
    global scheduler
    
    if scheduler is None:
        scheduler = AsyncIOScheduler()
        scheduler.start()
    
    # 添加日切报表任务
    try:
        scheduler.add_job(
            send_daily_report,
            trigger=CronTrigger(hour=23, minute=5),
            args=[bot],
            id="daily_report",
            replace_existing=True
        )
        logger.info("已设置日切报表任务: 每天 23:05 自动发送")
    except Exception as e:
        logger.error(f"设置日切报表任务失败: {e}", exc_info=True)

