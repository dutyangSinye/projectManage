"""Application time helpers.

The database currently stores naive ``DateTime`` values for compatibility.
They are application-local values in Asia/Shanghai, never UTC values.
"""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


APPLICATION_TIMEZONE_NAME = "Asia/Shanghai"
try:
    APPLICATION_TIMEZONE = ZoneInfo(APPLICATION_TIMEZONE_NAME)
except ZoneInfoNotFoundError:
    # Windows 开发环境可能没有系统 tzdata；上海全年固定为 UTC+8，
    # 生产容器通过 requirements.txt 使用标准时区数据库。
    APPLICATION_TIMEZONE = timezone(timedelta(hours=8), name=APPLICATION_TIMEZONE_NAME)


def now_local() -> datetime:
    """Return the current application time as a naive Asia/Shanghai value."""
    return datetime.now(APPLICATION_TIMEZONE).replace(tzinfo=None)


def today_local() -> date:
    """Return the current application date in Asia/Shanghai."""
    return now_local().date()
