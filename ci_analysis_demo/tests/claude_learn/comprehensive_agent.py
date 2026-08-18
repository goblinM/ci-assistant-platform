"""Comprehensive Agent 的向后兼容入口。

实现已按职责拆分，由 comprehensive_agent_modules 统一装配。
"""

import sys
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from ci_analysis_demo.tests.claude_learn.comprehensive_agent_modules import *  # noqa: F401,F403
from ci_analysis_demo.tests.claude_learn.comprehensive_agent_modules import main


if __name__ == "__main__":
    main()
