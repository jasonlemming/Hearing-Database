"""
Task manager for admin dashboard background operations

Manages subprocess-based update tasks with progress tracking and log streaming.
"""
import uuid
import subprocess
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any, TYPE_CHECKING
from dataclasses import dataclass, field, asdict
from enum import Enum

from config.logging_config import get_logger

if TYPE_CHECKING:
    from subprocess import Popen

logger = get_logger(__name__)


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskState:
    """State of a background task"""
    task_id: str
    command: List[str]
    status: TaskStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    subprocess: Optional['Popen'] = None
    stdout_buffer: List[str] = field(default_factory=list)
    stderr_buffer: List[str] = field(default_factory=list)
    progress_data: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    def duration_seconds(self) -> Optional[float]:
        """Calculate task duration in seconds"""
        if not self.end_time:
            # Task still running
            return (datetime.now() - self.start_time).total_seconds()
        return (self.end_time - self.start_time).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'task_id': self.task_id,
            'command': self.command,
            'status': self.status.value,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.duration_seconds(),
            'stdout_lines': len(self.stdout_buffer),
            'stderr_lines': len(self.stderr_buffer),
            'progress': self.progress_data,
            'result': self.result,
            'error_message': self.error_message
        }


class TaskManager:
    """
    Manages background tasks (subprocess-based updates) for admin dashboard

    Thread-safe singleton for tracking and controlling update operations.
    WARNING: Localhost use only - no authentication.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        """Initialize task storage"""
        if self._initialized:
            return

        self.tasks: Dict[str, TaskState] = {}
        self.max_stdout_lines = 10000  # Prevent memory issues
        self.max_stderr_lines = 1000
        self.task_ttl_hours = 1  # Clean up after 1 hour
        self._initialized = True

        logger.info("TaskManager initialized")

    def start_task(self, command: List[str]) -> str:
        """
        Start a new background task using subprocess

        Args:
            command: Command to execute as list (e.g. ["python3", "cli.py", "update", ...])

        Returns:
            task_id: Unique identifier for tracking

        Raises:
            RuntimeError: If another task is already running
        """
        # Check if any task is currently running
        if self._has_running_task():
            raise RuntimeError("Another update task is already running. Please wait for it to complete.")

        task_id = str(uuid.uuid4())

        logger.info(f"Starting task {task_id}: {' '.join(command)}")

        try:
            # Start subprocess with stdout/stderr capture
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True
            )

            # Create task state
            task = TaskState(
                task_id=task_id,
                command=command,
                status=TaskStatus.RUNNING,
                start_time=datetime.now(),
                subprocess=process
            )

            self.tasks[task_id] = task

            # Start thread to read stdout/stderr
            threading.Thread(target=self._read_output, args=(task_id,), daemon=True).start()

            logger.info(f"Task {task_id} started successfully (PID: {process.pid})")
            return task_id

        except Exception as e:
            logger.error(f"Failed to start task: {e}")
            raise

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current status of a task

        Args:
            task_id: Task identifier

        Returns:
            Task status dictionary or None if not found
        """
        task = self.tasks.get(task_id)
        if not task:
            return None

        # Check if subprocess has finished
        if task.subprocess and task.status == TaskStatus.RUNNING:
            returncode = task.subprocess.poll()
            if returncode is not None:
                # Process finished
                task.end_time = datetime.now()
                if returncode == 0:
                    task.status = TaskStatus.COMPLETED
                    logger.info(f"Task {task_id} completed successfully")
                else:
                    task.status = TaskStatus.FAILED
                    task.error_message = f"Process exited with code {returncode}"
                    logger.error(f"Task {task_id} failed with code {returncode}")

        return task.to_dict()

    def get_task_logs(self, task_id: str, since_line: int = 0) -> Optional[Dict[str, Any]]:
        """
        Get log output for a task

        Args:
            task_id: Task identifier
            since_line: Return only logs after this line number (for incremental updates)

        Returns:
            Dictionary with stdout and stderr arrays, or None if task not found
        """
        task = self.tasks.get(task_id)
        if not task:
            return None

        return {
            'stdout': task.stdout_buffer[since_line:],
            'stderr': task.stderr_buffer[since_line:],
            'total_stdout_lines': len(task.stdout_buffer),
            'total_stderr_lines': len(task.stderr_buffer)
        }

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running task by killing its subprocess

        Args:
            task_id: Task identifier

        Returns:
            True if cancelled, False if task not found or not running
        """
        task = self.tasks.get(task_id)
        if not task or task.status != TaskStatus.RUNNING:
            return False

        if task.subprocess:
            try:
                logger.info(f"Cancelling task {task_id} (PID: {task.subprocess.pid})")
                task.subprocess.kill()
                task.subprocess.wait(timeout=5)
                task.status = TaskStatus.CANCELLED
                task.end_time = datetime.now()
                logger.info(f"Task {task_id} cancelled successfully")
                return True
            except Exception as e:
                logger.error(f"Error cancelling task {task_id}: {e}")
                return False

        return False

    def cleanup_old_tasks(self) -> int:
        """
        Remove completed tasks older than TTL

        Returns:
            Number of tasks cleaned up
        """
        cutoff = datetime.now() - timedelta(hours=self.task_ttl_hours)
        to_remove = []

        for task_id, task in self.tasks.items():
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                if task.end_time and task.end_time < cutoff:
                    to_remove.append(task_id)

        for task_id in to_remove:
            logger.info(f"Cleaning up old task {task_id}")
            del self.tasks[task_id]

        return len(to_remove)

    def _has_running_task(self) -> bool:
        """Check if any task is currently running"""
        return any(task.status == TaskStatus.RUNNING for task in self.tasks.values())

    def _read_output(self, task_id: str):
        """
        Background thread to read subprocess output

        Reads stdout/stderr line by line and parses JSON progress updates.
        """
        task = self.tasks.get(task_id)
        if not task or not task.subprocess:
            return

        try:
            # Read stdout in real-time
            for line in iter(task.subprocess.stdout.readline, ''):
                if not line:
                    break

                line = line.rstrip()

                # Add to buffer (with size limit)
                if len(task.stdout_buffer) < self.max_stdout_lines:
                    task.stdout_buffer.append(line)

                # Try to parse as JSON progress update
                try:
                    data = json.loads(line)
                    if isinstance(data, dict):
                        # Update progress data
                        msg_type = data.get('type')

                        if msg_type == 'progress':
                            task.progress_data.update(data)
                        elif msg_type == 'complete':
                            task.result = data.get('metrics')
                        elif msg_type == 'error':
                            if not task.error_message:
                                task.error_message = data.get('message', 'Unknown error')

                except json.JSONDecodeError:
                    # Not JSON, just a regular log line
                    pass

            # Read stderr
            for line in iter(task.subprocess.stderr.readline, ''):
                if not line:
                    break

                line = line.rstrip()
                if len(task.stderr_buffer) < self.max_stderr_lines:
                    task.stderr_buffer.append(line)

            # Wait for process to complete
            task.subprocess.wait()

        except Exception as e:
            logger.error(f"Error reading output for task {task_id}: {e}")
            task.error_message = str(e)
            task.status = TaskStatus.FAILED
            task.end_time = datetime.now()


# Global singleton instance
task_manager = TaskManager()
