"""MCP 音频任务的 SQLite 持久化。"""

import sqlite3
from datetime import datetime, timezone


class DataBase:
    """保存音频任务状态，不保存 API Key 或音频正文。"""

    def __init__(self, db_name):
        self.db_name = db_name
        self.connection = None
        self.cursor = None

    def connect(self):
        """建立数据库连接并启用外键约束。"""
        # 当前数据库用于保存任务元数据，不保存音频二进制内容。
        self.connection = sqlite3.connect(self.db_name)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.connection.cursor()
        return self

    def initialize(self):
        """创建任务记录表。"""
        # IF NOT EXISTS 允许服务重复启动而不会重建已有任务记录。
        self.execute_query(
            """
            CREATE TABLE IF NOT EXISTS audio_tasks (
                task_id TEXT PRIMARY KEY,
                input_path TEXT NOT NULL,
                output_path TEXT,
                input_format TEXT NOT NULL,
                output_format TEXT,
                status TEXT NOT NULL,
                text TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                finished_at TEXT
            )
            """
        )

    def close(self):
        """关闭连接并清理游标。"""
        if self.connection:
            self.connection.close()
        self.connection = None
        self.cursor = None

    def execute_query(self, query, params=None):
        """执行写操作并提交事务。"""
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection is not established.")
        # 使用参数化 SQL，避免任务文本或路径被当作 SQL 代码执行。
        if params is not None:
            self.cursor.execute(query, params)
        else:
            self.cursor.execute(query)
        self.connection.commit()
        return self.cursor

    def fetch_all(self, query, params=None):
        """查询全部结果。"""
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection is not established.")
        if params is not None:
            self.cursor.execute(query, params)
        else:
            self.cursor.execute(query)
        return self.cursor.fetchall()

    def record_task(
        self,
        task_id,
        input_path,
        input_format,
        status="processing",
        output_path=None,
        output_format=None,
        text=None,
        error=None,
        finished_at=None,
    ):
        """新增或更新一次音频任务记录。"""
        # 使用 UTC 时间，便于不同部署环境统一比较任务时间。
        now = datetime.now(timezone.utc).isoformat()
        self.execute_query(
            """
            INSERT INTO audio_tasks (
                task_id, input_path, output_path, input_format, output_format,
                status, text, error, created_at, finished_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            -- 同一个任务先写入 processing，完成或失败时再更新状态。
            ON CONFLICT(task_id) DO UPDATE SET
                output_path = excluded.output_path,
                output_format = excluded.output_format,
                status = excluded.status,
                text = excluded.text,
                error = excluded.error,
                finished_at = excluded.finished_at
            """,
            (
                task_id,
                str(input_path),
                str(output_path) if output_path else None,
                input_format,
                output_format,
                status,
                text,
                str(error) if error else None,
                now,
                finished_at or (now if status in {"completed", "failed"} else None),
            ),
        )
