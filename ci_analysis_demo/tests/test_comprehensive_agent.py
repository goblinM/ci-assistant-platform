#!/usr/bin/env python3
"""
s20: Comprehensive Agent — all teaching components in one loop.
Run:  python s20_comprehensive/code.py
Need: pip install anthropic python-dotenv pyyaml + .env with ANTHROPIC_API_KEY
This final chapter intentionally puts the earlier teaching mechanisms back
together: dispatch, permission, hooks, todo, subagent, skills, compaction,
memory, prompt assembly, error recovery, task graph, background tasks, cron,
teams, protocols, autonomous agents, worktrees, and MCP.
"""
import ast, json, os, subprocess, time, random, threading, re
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field
import yaml
from openai import OpenAI

from ci_analysis_demo.tests.claude_learn.agent_loop import cron_autorun_loop
from ci_analysis_demo.tests.claude_learn.mcp_system import mcp_clients
from ci_analysis_demo.tests.claude_learn.pipeline_set import trigger_hooks
from ci_analysis_demo.tests.claude_learn.utils import active_teammates

try:
    import readline

    readline.parse_and_bind('set bind-tty-special-chars off')
    READLINE_AVAILABLE = True
except ImportError:
    READLINE_AVAILABLE = False
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)
if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

WORKDIR = Path.cwd()
client = OpenAI(base_url=os.getenv("LLM_API_URL"))
MODEL = os.getenv("LLM_MODEL")
PRIMARY_MODEL = MODEL
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL")
SKILLS_DIR = WORKDIR / "skills"
TRANSCRIPT_DIR = WORKDIR / ".transcripts"
TOOL_RESULTS_DIR = WORKDIR / ".task_outputs" / "tool-results"

DEFAULT_MAX_TOKENS = 8000
ESCALATE_MAX_TOKENS = 16000
MAX_RETRIES = 3
MAX_CONSECUTIVE_529 = 2
MAX_RECOVERY_RETRIES = 2
BASE_DELAY_MS = 500
CONTEXT_LIMIT = 50000
KEEP_RECENT_TOOL_RESULTS = 3
PERSIST_THRESHOLD = 30000
CONTINUATION_PROMPT = "Continue from the previous response. Do not repeat completed work."
PROMPT = "\033[36ms20 >> \033[0m"
CLI_ACTIVE = False

TASKS_DIR = WORKDIR / ".tasks"
TASKS_DIR.mkdir(exist_ok=True)
CURRENT_TOOLS: list[dict] = []

WORKTREES_DIR = WORKDIR / ".worktrees"
WORKTREES_DIR.mkdir(exist_ok=True)
VALID_WT_NAME = re.compile(r'^[A-Za-z0-9._-]{1,64}$')

# ── Context ──
MEMORY_DIR = WORKDIR / ".memory"
MEMORY_INDEX = MEMORY_DIR / "MEMORY.md"


def update_context(context: dict, messages: list) -> dict:
    memories = ""
    if MEMORY_INDEX.exists():
        memories = MEMORY_INDEX.read_text()[:2000]
    return {
        "memories": memories,
        "connected_mcp": list(mcp_clients.keys()),
        "active_teammates": list(active_teammates.keys()),
    }


if __name__ == "__main__":
    CLI_ACTIVE = True
    print("s20: comprehensive agent")
    print("Enter a question, press Enter to send. Type q to quit.\n")
    history = []
    context = update_context({}, [])
    threading.Thread(target=cron_autorun_loop,
                     args=(history, context), daemon=True).start()
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
            def inbox_label(msg):
                req_id = msg.get("metadata", {}).get("request_id", "")
                suffix = f" req:{req_id}" if req_id else ""
                return f"{msg.get('type', 'message')}{suffix}"
            inbox_text = "\n".join(
                f"From {m['from']} [{inbox_label(m)}]: "
                f"{m['content'][:200]}" for m in inbox)
            history.append({"role": "user",
                            "content": f"[Inbox]\n{inbox_text}"})
        print()