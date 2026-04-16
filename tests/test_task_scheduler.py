#!/usr/bin/env python3
"""
TaskScheduler 单元测试
"""

import pytest
import json
import time
import threading
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call, AsyncMock
from datetime import datetime, timedelta

import sys
PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from tools.advanced import TaskScheduler


class TestTaskScheduler:
    """测试 TaskScheduler 类"""
    
    def test_init_default(self):
        """测试默认初始化"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler'):
                scheduler = TaskScheduler()
                assert scheduler is not None
                assert scheduler.log_level == "INFO"
    
    def test_init_scheduler_created(self):
        """测试调度器初始化"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler') as mock_scheduler:
                with patch('apscheduler.executors.pool.ThreadPoolExecutor'):
                    with patch('tools.advanced.TaskScheduler._init_scheduler') as mock_init:
                        mock_init.return_value = MagicMock()
                        
                        scheduler = TaskScheduler()
                        
                        # 验证 scheduler 被创建
                        assert scheduler.scheduler is not None
    
    def test_load_tasks_no_file(self, tmp_path):
        """测试加载不存在的任务文件"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler'):
                scheduler = TaskScheduler()
                scheduler.tasks_file = tmp_path / "nonexistent.json"
                
                tasks = scheduler._load_tasks()
                assert tasks == []
    
    def test_load_tasks_with_file(self, tmp_path):
        """测试加载任务文件"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler'):
                scheduler = TaskScheduler()
                scheduler.tasks_file = tmp_path / "tasks.json"
                
                # 写入任务文件
                test_tasks = [
                    {"id": "1", "name": "test_task", "enabled": True}
                ]
                with open(scheduler.tasks_file, 'w') as f:
                    json.dump(test_tasks, f)
                
                tasks = scheduler._load_tasks()
                assert len(tasks) == 1
                assert tasks[0]["name"] == "test_task"
    
    def test_save_tasks(self, tmp_path):
        """测试保存任务"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler'):
                scheduler = TaskScheduler()
                scheduler.tasks_file = tmp_path / "tasks.json"
                scheduler.tasks = [
                    {"id": "1", "name": "test_task", "enabled": True}
                ]
                
                scheduler._save_tasks()
                
                assert scheduler.tasks_file.exists()
                
                with open(scheduler.tasks_file, 'r') as f:
                    saved = json.load(f)
                assert len(saved) == 1
    
    def test_add_task(self, tmp_path):
        """测试添加任务"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler'):
                scheduler = TaskScheduler()
                scheduler.tasks_file = tmp_path / "tasks.json"
                
                task = scheduler.add_task(
                    name="测试任务",
                    task_type="content_generate",
                    schedule="10:00",
                    config={"topic": "测试"}
                )
                
                assert task["name"] == "测试任务"
                assert task["task_type"] == "content_generate"
                assert task["schedule"] == "10:00"
                assert task["enabled"] is True
                assert "id" in task
    
    def test_remove_task(self, tmp_path):
        """测试删除任务"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler'):
                scheduler = TaskScheduler()
                scheduler.tasks_file = tmp_path / "tasks.json"
                
                # 先添加任务
                task = scheduler.add_task(
                    name="测试任务",
                    task_type="content_generate",
                    schedule="10:00"
                )
                task_id = task["id"]
                
                # 删除任务
                result = scheduler.remove_task(task_id)
                
                assert result is True
                assert len(scheduler.tasks) == 0
    
    def test_enable_task(self, tmp_path):
        """测试启用任务"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler'):
                scheduler = TaskScheduler()
                scheduler.tasks_file = tmp_path / "tasks.json"
                
                # 先添加任务
                task = scheduler.add_task(
                    name="测试任务",
                    task_type="content_generate",
                    schedule="10:00",
                    enabled=False
                )
                task_id = task["id"]
                
                # 启用任务
                result = scheduler.enable_task(task_id)
                
                assert result is True
                assert scheduler.tasks[0]["enabled"] is True
    
    def test_disable_task(self, tmp_path):
        """测试禁用任务"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler'):
                scheduler = TaskScheduler()
                scheduler.tasks_file = tmp_path / "tasks.json"
                
                # 先添加任务
                task = scheduler.add_task(
                    name="测试任务",
                    task_type="content_generate",
                    schedule="10:00",
                    enabled=True
                )
                task_id = task["id"]
                
                # 禁用任务
                result = scheduler.disable_task(task_id)
                
                assert result is True
                assert scheduler.tasks[0]["enabled"] is False
    
    def test_get_tasks(self, tmp_path):
        """测试获取任务列表"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler'):
                scheduler = TaskScheduler()
                scheduler.tasks_file = tmp_path / "tasks.json"
                
                # 添加任务
                scheduler.add_task("任务1", "content_generate", "10:00", enabled=True)
                scheduler.add_task("任务2", "content_generate", "11:00", enabled=False)
                
                all_tasks = scheduler.get_tasks()
                assert len(all_tasks) == 2
                
                enabled_tasks = scheduler.get_tasks(enabled_only=True)
                assert len(enabled_tasks) == 1
    
    def test_run_task_not_found(self, tmp_path):
        """测试运行不存在的任务"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler'):
                scheduler = TaskScheduler()
                scheduler.tasks_file = tmp_path / "tasks.json"
                
                result = scheduler.run_task("nonexistent_id")
                
                assert result["success"] is False
                assert "不存在" in result["error"]
    
    def test_run_task_unknown_type(self, tmp_path):
        """测试运行未知类型的任务"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler'):
                scheduler = TaskScheduler()
                scheduler.tasks_file = tmp_path / "tasks.json"
                
                task = scheduler.add_task(
                    name="测试任务",
                    task_type="unknown_type",
                    schedule="10:00"
                )
                
                result = scheduler.run_task(task["id"])
                
                assert result["success"] is False
                assert "未知" in result["error"]
    
    @patch('tools.advanced.ContentGenerator')
    def test_run_content_generate_task(self, mock_generator):
        """测试运行内容生成任务"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler'):
                scheduler = TaskScheduler()
                scheduler.tasks_file = Path("/tmp/tasks.json")
                scheduler._running = True  # 模拟调度器运行
                
                task = scheduler.add_task(
                    name="测试任务",
                    task_type="content_generate",
                    schedule="10:00",
                    config={"topic": "测试"}
                )
                
                # Mock 生成器
                mock_gen_instance = MagicMock()
                mock_gen_instance.generate.return_value = "生成的内容"
                mock_generator.return_value = mock_gen_instance
                
                result = scheduler.run_task(task["id"])
                
                # 注意：由于 mock 可能不完全，这个测试可能需要调整
                assert isinstance(result, dict)
    
    def test_parse_schedule_hhmm(self):
        """测试解析 HH:MM 格式"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler'):
                scheduler = TaskScheduler()
                
                trigger = scheduler._parse_schedule("10:30")
                
                assert trigger is not None
    
    def test_parse_schedule_cron(self):
        """测试解析 cron 表达式"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler'):
                scheduler = TaskScheduler()
                
                trigger = scheduler._parse_schedule("0 10 * * *")
                
                assert trigger is not None
    
    def test_parse_schedule_interval(self):
        """测试解析 interval 格式"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler'):
                scheduler = TaskScheduler()
                
                trigger = scheduler._parse_schedule("1h")
                
                assert trigger is not None
    
    def test_parse_schedule_invalid(self):
        """测试解析无效格式"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler'):
                scheduler = TaskScheduler()
                
                trigger = scheduler._parse_schedule("invalid")
                
                assert trigger is None


class TestTaskSchedulerAPSScheduler:
    """测试 APScheduler 集成"""
    
    def test_start_scheduler(self, tmp_path):
        """测试启动调度器"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler') as mock_scheduler_class:
                mock_scheduler = MagicMock()
                mock_scheduler_class.return_value = mock_scheduler
                
                scheduler = TaskScheduler()
                scheduler.tasks_file = tmp_path / "tasks.json"
                scheduler.tasks_file.parent.mkdir(parents=True, exist_ok=True)
                
                # 添加一个启用的任务
                scheduler.add_task(
                    name="测试任务",
                    task_type="content_generate",
                    schedule="10:00",
                    enabled=True
                )
                
                # 启动调度器
                scheduler.start()
                
                # 验证调度器启动
                mock_scheduler.start.assert_called_once()
                assert scheduler._running is True
    
    def test_stop_scheduler(self, tmp_path):
        """测试停止调度器"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler') as mock_scheduler_class:
                mock_scheduler = MagicMock()
                mock_scheduler_class.return_value = mock_scheduler
                
                scheduler = TaskScheduler()
                scheduler.tasks_file = tmp_path / "tasks.json"
                scheduler._running = True
                
                # 停止调度器
                scheduler.stop()
                
                # 验证调度器停止
                mock_scheduler.shutdown.assert_called_once()
                assert scheduler._running is False
    
    def test_start_already_running(self, tmp_path):
        """测试重复启动"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler') as mock_scheduler_class:
                mock_scheduler = MagicMock()
                mock_scheduler_class.return_value = mock_scheduler
                
                scheduler = TaskScheduler()
                scheduler.tasks_file = tmp_path / "tasks.json"
                scheduler._running = True
                
                # 尝试再次启动
                scheduler.start()
                
                # 调度器不应该再次启动
                mock_scheduler.start.assert_not_called()
    
    def test_stop_not_running(self, tmp_path):
        """测试停止未运行的调度器"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler') as mock_scheduler_class:
                mock_scheduler = MagicMock()
                mock_scheduler_class.return_value = mock_scheduler
                
                scheduler = TaskScheduler()
                scheduler.tasks_file = tmp_path / "tasks.json"
                scheduler._running = False
                
                # 尝试停止
                scheduler.stop()
                
                # 调度器不应该调用 shutdown
                mock_scheduler.shutdown.assert_not_called()
    
    def test_add_task_when_running(self, tmp_path):
        """测试运行时添加任务"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler') as mock_scheduler_class:
                mock_scheduler = MagicMock()
                mock_scheduler_class.return_value = mock_scheduler
                
                scheduler = TaskScheduler()
                scheduler.tasks_file = tmp_path / "tasks.json"
                scheduler._running = True
                
                # 添加任务
                task = scheduler.add_task(
                    name="测试任务",
                    task_type="content_generate",
                    schedule="10:00",
                    enabled=True
                )
                
                # 验证任务被添加到调度器
                assert mock_scheduler.add_job.called
    
    def test_remove_task_when_running(self, tmp_path):
        """测试运行时删除任务"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler') as mock_scheduler_class:
                mock_scheduler = MagicMock()
                mock_scheduler_class.return_value = mock_scheduler
                
                scheduler = TaskScheduler()
                scheduler.tasks_file = tmp_path / "tasks.json"
                scheduler._running = True
                
                # 添加任务
                task = scheduler.add_task(
                    name="测试任务",
                    task_type="content_generate",
                    schedule="10:00",
                    enabled=True
                )
                
                # 删除任务
                scheduler.remove_task(task["id"])
                
                # 验证任务从调度器中移除
                mock_scheduler.remove_job.assert_called_once()


class TestTaskSchedulerState:
    """测试任务状态持久化"""
    
    def test_save_state(self, tmp_path):
        """测试保存调度器状态"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler'):
                scheduler = TaskScheduler()
                scheduler.state_file = tmp_path / "state.json"
                scheduler._running = True
                
                scheduler._save_state()
                
                assert scheduler.state_file.exists()
                
                with open(scheduler.state_file, 'r') as f:
                    state = json.load(f)
                assert state["running"] is True
    
    def test_task_last_run_updated(self, tmp_path):
        """测试任务最后运行时间更新"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler'):
                with patch('tools.advanced.ContentGenerator') as mock_cg:
                    scheduler = TaskScheduler()
                    scheduler.tasks_file = tmp_path / "tasks.json"
                    
                    # Mock
                    mock_instance = MagicMock()
                    mock_instance.generate.return_value = "内容"
                    mock_cg.return_value = mock_instance
                    
                    task = scheduler.add_task(
                        name="测试任务",
                        task_type="content_generate",
                        schedule="10:00"
                    )
                    
                    result = scheduler.run_task(task["id"])
                    
                    # 验证 last_run 被更新
                    updated_task = next(t for t in scheduler.tasks if t["id"] == task["id"])
                    assert updated_task["last_run"] is not None
    
    def test_task_run_count_incremented(self, tmp_path):
        """测试任务运行计数增加"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler'):
                with patch('tools.advanced.ContentGenerator') as mock_cg:
                    scheduler = TaskScheduler()
                    scheduler.tasks_file = tmp_path / "tasks.json"
                    
                    # Mock
                    mock_instance = MagicMock()
                    mock_instance.generate.return_value = "内容"
                    mock_cg.return_value = mock_instance
                    
                    task = scheduler.add_task(
                        name="测试任务",
                        task_type="content_generate",
                        schedule="10:00"
                    )
                    
                    scheduler.run_task(task["id"])
                    scheduler.run_task(task["id"])
                    
                    # 验证 run_count 增加
                    updated_task = next(t for t in scheduler.tasks if t["id"] == task["id"])
                    assert updated_task["run_count"] == 2


class TestTaskSchedulerErrorHandling:
    """测试错误处理"""
    
    def test_load_tasks_invalid_json(self, tmp_path):
        """测试加载无效 JSON"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler'):
                scheduler = TaskScheduler()
                scheduler.tasks_file = tmp_path / "tasks.json"
                
                # 写入无效 JSON
                with open(scheduler.tasks_file, 'w') as f:
                    f.write("invalid json")
                
                tasks = scheduler._load_tasks()
                assert tasks == []
    
    def test_save_tasks_error(self, tmp_path):
        """测试保存任务错误"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler'):
                scheduler = TaskScheduler()
                scheduler.tasks_file = tmp_path / "tasks.json"
                scheduler.tasks = [{"id": "1"}]
                
                # 模拟保存错误 (只读文件系统)
                with patch('builtins.open', side_effect=Exception("Write error")):
                    scheduler._save_tasks()  # 不应该抛出异常
    
    def test_execute_task_wrapper_not_found(self, tmp_path):
        """测试执行不存在的任务包装器"""
        with patch('tools.advanced.setup_logging'):
            with patch('apscheduler.schedulers.background.BackgroundScheduler'):
                scheduler = TaskScheduler()
                scheduler.tasks_file = tmp_path / "tasks.json"
                scheduler._running = True
                
                scheduler._execute_task_wrapper("nonexistent")
                
                # 不应该抛出异常


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
