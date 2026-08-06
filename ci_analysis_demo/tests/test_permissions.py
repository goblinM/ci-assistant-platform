"""
harness permission
three gates:
gate1: hard deny
gate2: rule matching
gate3: user approval
"""


class TestGatesPermission(object):
    def __init__(self):
        self.DENY_LIST = [
            "rm -rf /", "sudo", "shutdown", "reboot",
            "mkfs", "dd if=", "> /dev/sda",
        ]

        self.PERMISSION_RULES = [
            {
                "tools": ["write_file", "edit_file"],
                "check": lambda args: not (WORKDIR / args.get("path", "")).resolve().is_relative_to(WORKDIR),
                "message": "Writing outside workspace",
            },
            {
                "tools": ["bash"],
                "check": lambda args: any(kw in args.get("command", "") for kw in ["rm ", "> /etc/", "chmod 777"]),
                "message": "Potentially destructive command",
            },
        ]

    def check_deny_list(self, command: str) -> str | None:
        for pattern in self.DENY_LIST:
            if pattern in command:
                return f"Blocked: '{pattern}' is on the deny list"
        return None

    def check_rules(self, tool_name: str, args: dict) -> str | None:
        for rule in self.PERMISSION_RULES:
            if tool_name in rule["tools"] and rule["check"](args):
                return rule["message"]
        return None

    def ask_user(self, tool_name: str, args: dict, reason: str) -> str:
        print(f"\n⚠  {reason}")
        print(f"   Tool: {tool_name}({args})")
        choice = input("   Allow? [y/N] ").strip().lower()
        return "allow" if choice in ("y", "yes") else "deny"

    def check_permission(self, block) -> bool:
        # Gate 1: Hard deny
        if block.name == "bash":
            reason = self.check_deny_list(block.input.get("command", ""))
            if reason:
                print(f"\n⛔ {reason}")
                return False

        # Gate 2 + 3: Rule matching → User approval
        reason = self.check_rules(block.name, block.input)
        if reason:
            decision = self.ask_user(block.name, block.input, reason)
            if decision == "deny":
                return False

        return True

    # # In agent_loop — s02's loop with just one line added:
    # for block in response.content:
    #     if block.type == "tool_use":
    #         if not check_permission(block):  # ← NEW
    #             results.append({..."content": "Permission denied."})
    #             continue
    #         output = TOOL_HANDLERS[block.name](**block.input)  # s02 original
    #         results.append(...)
