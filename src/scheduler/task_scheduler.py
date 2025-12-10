"""
Task Scheduler
Handles scheduled tasks like daily profile logging and data collection
"""

import schedule
import time
import logging
from datetime import datetime, timedelta
from typing import Callable, Dict, Any, Optional
from threading import Thread, Event
import pytz


class TaskScheduler:
    """Manages scheduled tasks for the trading bot"""

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize Task Scheduler

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        self.running = False
        self.stop_event = Event()
        self.scheduler_thread: Optional[Thread] = None

        # Task registry
        self.tasks = {}

    def add_task(
        self,
        name: str,
        func: Callable,
        schedule_type: str,
        schedule_time: str = None,
        interval: int = None,
        **kwargs
    ):
        """
        Add a scheduled task

        Args:
            name: Unique task name
            func: Function to execute
            schedule_type: Type of schedule ('daily', 'hourly', 'interval', 'cron')
            schedule_time: Time string for daily tasks (e.g., "09:30")
            interval: Interval in minutes for interval-based tasks
            **kwargs: Additional arguments to pass to the function
        """
        task_config = {
            'func': func,
            'schedule_type': schedule_type,
            'schedule_time': schedule_time,
            'interval': interval,
            'kwargs': kwargs
        }

        self.tasks[name] = task_config

        # Schedule the task
        if schedule_type == 'daily':
            schedule.every().day.at(schedule_time).do(self._run_task, name)
            self.logger.info(f"Scheduled daily task '{name}' at {schedule_time}")

        elif schedule_type == 'hourly':
            schedule.every().hour.do(self._run_task, name)
            self.logger.info(f"Scheduled hourly task '{name}'")

        elif schedule_type == 'interval':
            schedule.every(interval).minutes.do(self._run_task, name)
            self.logger.info(f"Scheduled interval task '{name}' every {interval} minutes")

        else:
            self.logger.warning(f"Unknown schedule type: {schedule_type}")

    def _run_task(self, task_name: str):
        """
        Execute a scheduled task

        Args:
            task_name: Name of task to execute
        """
        if task_name not in self.tasks:
            self.logger.error(f"Task '{task_name}' not found")
            return

        task = self.tasks[task_name]

        try:
            self.logger.info(f"Executing task: {task_name}")
            start_time = datetime.now()

            # Execute the task function
            func = task['func']
            kwargs = task.get('kwargs', {})
            func(**kwargs)

            elapsed = (datetime.now() - start_time).total_seconds()
            self.logger.info(f"Task '{task_name}' completed in {elapsed:.2f}s")

        except Exception as e:
            self.logger.error(f"Error executing task '{task_name}': {e}", exc_info=True)

    def remove_task(self, task_name: str):
        """
        Remove a scheduled task

        Args:
            task_name: Name of task to remove
        """
        if task_name in self.tasks:
            del self.tasks[task_name]
            self.logger.info(f"Removed task: {task_name}")

    def start(self):
        """Start the scheduler in a background thread"""
        if self.running:
            self.logger.warning("Scheduler already running")
            return

        self.running = True
        self.stop_event.clear()

        # Start scheduler thread
        self.scheduler_thread = Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()

        self.logger.info("Task scheduler started")

    def _run_scheduler(self):
        """Run the scheduler loop"""
        while self.running and not self.stop_event.is_set():
            schedule.run_pending()
            time.sleep(1)

    def stop(self):
        """Stop the scheduler"""
        if not self.running:
            return

        self.running = False
        self.stop_event.set()

        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)

        self.logger.info("Task scheduler stopped")

    def setup_default_tasks(self, bot_instance):
        """
        Set up default scheduled tasks

        Args:
            bot_instance: Reference to the main bot instance
        """
        scheduling_config = self.config.get('scheduling', {})

        # Daily profile logging
        daily_profile_time = scheduling_config.get('daily_profile_time', '23:55')
        self.add_task(
            name='daily_profile',
            func=bot_instance.save_daily_profiles,
            schedule_type='daily',
            schedule_time=daily_profile_time
        )

        # Data collection (every 5 minutes by default)
        self.add_task(
            name='data_update',
            func=bot_instance.update_data,
            schedule_type='interval',
            interval=5
        )

        # Cleanup old data (daily at midnight)
        cleanup_days = scheduling_config.get('cleanup_old_data_days', 90)
        self.add_task(
            name='data_cleanup',
            func=bot_instance.cleanup_old_data,
            schedule_type='daily',
            schedule_time='00:00',
            days=cleanup_days
        )

        self.logger.info("Default tasks configured")

    def get_next_run_time(self, task_name: str) -> Optional[datetime]:
        """
        Get the next scheduled run time for a task

        Args:
            task_name: Name of the task

        Returns:
            Next run time or None
        """
        for job in schedule.jobs:
            if job.job_func.args and job.job_func.args[0] == task_name:
                return job.next_run

        return None

    def list_tasks(self) -> Dict[str, Dict]:
        """
        Get list of all scheduled tasks

        Returns:
            Dictionary of task information
        """
        task_info = {}

        for name, config in self.tasks.items():
            next_run = self.get_next_run_time(name)
            task_info[name] = {
                'schedule_type': config['schedule_type'],
                'schedule_time': config.get('schedule_time'),
                'interval': config.get('interval'),
                'next_run': next_run
            }

        return task_info

    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()
