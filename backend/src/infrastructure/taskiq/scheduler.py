from taskiq import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource

from src.core.logging import configure_logging
from src.core.settings import get_settings
from src.infrastructure.taskiq.broker import broker

configure_logging("scheduler", get_settings().logging)

scheduler = TaskiqScheduler(
    broker=broker,
    sources=[LabelScheduleSource(broker)],
)
