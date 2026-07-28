"""
简单的计时工具
"""
import time
from contextlib import contextmanager


@contextmanager
def timer():
    """执行 ``timer`` 对应的领域操作。"""
    start = time.perf_counter()
    result = {"duration_ms": 0.0}
    try:
        yield result
    finally:
        result["duration_ms"] = round((time.perf_counter() - start) * 1000, 2)
