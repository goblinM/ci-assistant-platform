from __future__ import annotations

import re

from ci_assistant.knowledge.processing import mask_secrets


def preprocess_log(log: str, *, max_chars: int = 60_000) -> str:
    """执行 ``preprocess_log`` 对应的领域操作。"""
    cleaned = re.sub(r"\x1b\[[0-9;]*m", "", log.replace("\x00", ""))
    cleaned = mask_secrets(cleaned)
    lines = cleaned.splitlines()
    important = [
        line
        for line in lines
        if re.search(
            r"(?i)(error|exception|failed|failure|traceback|fatal|denied|timeout)",
            line,
        )
    ]
    selected = important[-300:] if important else lines[-500:]
    return "\n".join(selected)[-max_chars:]

