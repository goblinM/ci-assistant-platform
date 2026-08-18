"""装配拆分后的 Comprehensive Agent 教学模块。"""

import sys
import threading
from pathlib import Path

if __package__:
    from . import utils as _utils
    from .utils import *  # noqa: F401,F403
    from .pipeline_set import *  # noqa: F401,F403
    from .mcp_system import *  # noqa: F401,F403
    from .agent_loop import *  # noqa: F401,F403
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from ci_analysis_demo.tests.claude_learn import utils as _utils
    from ci_analysis_demo.tests.claude_learn.utils import *  # noqa: F401,F403
    from ci_analysis_demo.tests.claude_learn.pipeline_set import *  # noqa: F401,F403
    from ci_analysis_demo.tests.claude_learn.mcp_system import *  # noqa: F401,F403
    from ci_analysis_demo.tests.claude_learn.agent_loop import *  # noqa: F401,F403


def main() -> None:
    """启动交互式 Comprehensive Agent 教学循环。"""
    _utils.CLI_ACTIVE = True
    print("s20: comprehensive agent")
    print("Enter a question, press Enter to send. Type q to quit.\n")
    history = []
    context = update_context({}, [])
    # 定时任务
    threading.Thread(
        target=cron_autorun_loop, args=(history, context), daemon=True
    ).start()
    while True:
        try:
            query = input(PROMPT)
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        trigger_hooks("UserPromptSubmit", query)
        turn_start = len(history)
        history.append({"role": "user", "content": query})
        with agent_lock:
            agent_loop(history, context)
            context = update_context(context, history)
            print_turn_assistants(history, turn_start)
        inbox = consume_lead_inbox(route_protocol=True)
        if inbox:
            inbox_text = "\n".join(
                f"From {msg['from']} [{msg.get('type', 'message')}]: "
                f"{msg['content'][:200]}"
                for msg in inbox
            )
            history.append({"role": "user", "content": f"[Inbox]\n{inbox_text}"})
        print()


if __name__ == "__main__":
    main()
