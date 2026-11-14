import json
from pathlib import Path
from app.execution.workspace import BoundaryError

TOOL_NAMES = [
    "read_file",
    "search_files",
    "list_directory",
    "apply_patch",
    "execute_command",
    "git_diff",
    "write_test",
]
PROPERTIES = {
    "read_file": {"path": {"type": "string"}},
    "search_files": {"query": {"type": "string"}},
    "list_directory": {},
    "apply_patch": {"path": {"type": "string"}, "content": {"type": "string"}},
    "execute_command": {"command": {"type": "array", "items": {"type": "string"}}},
    "git_diff": {},
    "write_test": {"name": {"type": "string"}, "content": {"type": "string"}},
}


def tool_specs(role):
    allowed = {"read_file", "search_files", "list_directory", "git_diff"}
    if role == "engineer":
        allowed |= {"apply_patch", "execute_command"}
    if role == "tester":
        allowed |= {"write_test"}
    return [
        {
            "type": "function",
            "function": {
                "name": n,
                "description": "Write complete UTF-8 file contents" if n == "apply_patch" else n,
                "parameters": {
                    "type": "object",
                    "properties": PROPERTIES[n],
                    "required": list(PROPERTIES[n]),
                    "additionalProperties": False,
                },
            },
        }
        for n in TOOL_NAMES
        if n in allowed
    ]


class Tools:
    def __init__(self, workspace, sandbox, validation: Path, tick, audit=None):
        self.workspace, self.sandbox, self.validation, self.tick = workspace, sandbox, validation, tick
        self.audit = audit or (lambda *args: None)

    def call(self, role, name, args):
        self.tick()
        allowed = {x["function"]["name"] for x in tool_specs(role)}
        if name not in allowed:
            raise PermissionError(f"{role} cannot use {name}")
        if name == "read_file":
            result = self.workspace.safe(args["path"]).read_text()[:24000]
        elif name == "list_directory":
            result = self.workspace.files()
        elif name == "search_files":
            query = args["query"]
            result = []
            for filename in self.workspace.files():
                try:
                    if query.lower() in self.workspace.safe(filename).read_text()[:100000].lower():
                        result.append(filename)
                except UnicodeError:
                    pass
        elif name == "apply_patch":
            p = self.workspace.safe(args["path"], writable=True)
            if len(args["content"].encode()) > 200000:
                raise BoundaryError("File exceeds tool write limit")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(args["content"])
            p.chmod(0o644)
            result = {"written": args["path"]}
        elif name == "write_test":
            n = args["name"]
            if Path(n).name != n or not n.startswith("test_") or not n.endswith(".py"):
                raise BoundaryError("Test name must be a flat test_*.py filename")
            if len(args["content"].encode()) > 50000:
                raise BoundaryError("Generated test too large")
            (self.validation / "generated").mkdir(parents=True, exist_ok=True)
            (self.validation / "generated").chmod(0o755)
            (self.validation / "generated" / n).write_text(args["content"])
            (self.validation / "generated" / n).chmod(0o644)
            result = {"generated": n}
        elif name == "git_diff":
            result = self.workspace.diff()
        elif name == "execute_command":
            command = args["command"]
            if command != ["pytest", "-q", "-p", "no:cacheprovider", "tests"]:
                raise PermissionError("Engineer command must match the configured development check exactly")
            result = self.sandbox.execute(self.workspace.path, command).dump()
        else:
            raise PermissionError("Unknown tool")
        self.audit(role, name, args, result)
        return result
