"""
日志
"""
import logging


def setup_logger():
    """执行 ``setup_logger`` 对应的领域操作。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
