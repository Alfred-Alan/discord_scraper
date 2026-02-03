#!/usr/bin/env python3
"""
Cron Job Scheduler - 定时任务调度器

基于 APScheduler 的异步定时任务调度器
使用示例:
    scheduler = CronJobScheduler()
    await scheduler.add_job("job1", "*/5 * * * *", my_async_func, arg1, arg2)
    await scheduler.start()
    # 保持运行
    await scheduler.wait()
"""

import logging
from typing import Callable, Any, Optional, List, Dict
from dataclasses import dataclass

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.job import Job
    AP_SCHEDULER_AVAILABLE = True
except ImportError:
    AP_SCHEDULER_AVAILABLE = False
    AsyncIOScheduler = None
    CronTrigger = None
    Job = None

logger = logging.getLogger('cron_scheduler')


@dataclass
class JobConfig:
    """任务配置"""
    job_id: str
    cron_expr: str  # cron 表达式，如 "*/5 * * * *"
    func: Callable
    args: tuple = ()
    kwargs: dict = None

    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}


class CronJobScheduler:
    """
    Cron 任务调度器

    类似 Go 的 cron.Cron，支持异步任务调度
    """

    def __init__(self, timezone: str = "Asia/Shanghai"):
        """
        初始化调度器

        Args:
            timezone: 时区，默认 Asia/Shanghai
        """
        if not AP_SCHEDULER_AVAILABLE:
            raise ImportError(
                "APScheduler not installed. "
                "Please install: pip install apscheduler"
            )

        self.scheduler = AsyncIOScheduler(timezone=timezone)
        self.entries: dict[str, Job] = {}  # job_id -> Job 映射
        self._running = False

        logger.info("CronJobScheduler initialized")

    async def add_job(
        self,
        job_id: str,
        cron_expr: str,
        func: Callable,
        *args,
        **kwargs
    ) -> bool:
        """
        添加定时任务

        Args:
            job_id: 任务唯一标识
            cron_expr: Cron 表达式 (分 时 日 月 周)
                      例如: "*/5 * * * *" 每5分钟
                           "0 * * * *" 每小时
                           "0 9 * * 1-5" 工作日9点
            func: 异步函数
            *args: 函数位置参数
            **kwargs: 函数关键字参数

        Returns:
            bool: 是否添加成功
        """
        # 如果已存在相同 job_id，先移除
        if job_id in self.entries:
            await self.remove_job(job_id)

        try:
            # 解析 cron 表达式
            # APScheduler 的 CronTrigger 格式: minute hour day month day_of_week
            parts = cron_expr.split()
            if len(parts) != 5:
                logger.error(f"Invalid cron expression: {cron_expr}, expected 5 parts")
                return False

            trigger = CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
            )

            # 添加任务
            job = self.scheduler.add_job(
                func=func,
                trigger=trigger,
                args=args,
                kwargs=kwargs,
                id=job_id,
                replace_existing=True,
                max_instances=1,  # 同一任务同时只能运行一个实例
                coalesce=True,    # 如果错过了执行时间，只执行一次
            )

            self.entries[job_id] = job
            logger.info(f"Job added: {job_id}, cron: {cron_expr}")
            return True

        except Exception as e:
            logger.error(f"Failed to add job {job_id}: {e}")
            return False

    async def remove_job(self, job_id: str) -> bool:
        """
        移除定时任务

        Args:
            job_id: 任务标识

        Returns:
            bool: 是否移除成功
        """
        if job_id not in self.entries:
            return False

        try:
            self.scheduler.remove_job(job_id)
            del self.entries[job_id]
            logger.info(f"Job removed: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {e}")
            return False

    async def start(self):
        """启动调度器"""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self.scheduler.start()
        self._running = True
        logger.info("CronJobScheduler started")

    async def stop(self):
        """停止调度器"""
        if not self._running:
            return

        self.scheduler.shutdown(wait=True)
        self._running = False
        self.entries.clear()
        logger.info("CronJobScheduler stopped")

    async def wait(self):
        """
        阻塞等待调度器运行（保持程序不退出）

        适用于主程序需要保持运行的场景
        """
        import asyncio
        while self._running:
            await asyncio.sleep(1)

    def get_job_info(self, job_id: str) -> Optional[dict]:
        """获取任务信息"""
        if job_id not in self.entries:
            return None

        job = self.entries[job_id]
        return {
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time,
            "trigger": str(job.trigger),
        }

    def list_jobs(self) -> List[Dict]:
        """列出所有任务"""
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time,
            }
            for job in self.scheduler.get_jobs()
        ]

    def pause_job(self, job_id: str) -> bool:
        """暂停任务"""
        if job_id not in self.entries:
            return False
        try:
            job = self.entries[job_id]
            job.pause()
            logger.info(f"Job paused: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to pause job {job_id}: {e}")
            return False

    def resume_job(self, job_id: str) -> bool:
        """恢复任务"""
        if job_id not in self.entries:
            return False
        try:
            job = self.entries[job_id]
            job.resume()
            logger.info(f"Job resumed: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to resume job {job_id}: {e}")
            return False


# 便捷函数：创建调度器并添加任务
async def run_scheduled_job(
    cron_expr: str,
    func: Callable,
    *args,
    job_id: str = "default_job",
    **kwargs
):
    """
    快速启动一个定时任务并保持运行

    Args:
        cron_expr: Cron 表达式
        func: 要执行的函数
        *args: 函数参数
        job_id: 任务ID
        **kwargs: 函数关键字参数

    Example:
        async def my_task():
            print("Task running")

        await run_scheduled_job("*/5 * * * *", my_task)
    """
    scheduler = CronJobScheduler()

    await scheduler.add_job(job_id, cron_expr, func, *args, **kwargs)
    await scheduler.start()

    try:
        await scheduler.wait()
    except KeyboardInterrupt:
        await scheduler.stop()
