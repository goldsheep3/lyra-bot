#!/usr/bin/env python3
"""Fix: adapt kadou for new nonebot-plugin-locales Depends API."""
import re, sys

path = sys.argv[1] if len(sys.argv) > 1 else "plugins/kadou/__init__.py"

with open(path, "r") as f:
    lines = f.readlines()

# Track changes
changes = []
new_lines = []

for i, line in enumerate(lines):
    stripped = line.rstrip("\n")
    
    # 1. format_status: add `reply` first param
    if re.match(r'^async def format_status\(', stripped):
        new_lines.append("async def format_status(reply, " + stripped[len("async def format_status("):] + "\n")
        changes.append(f"L{i+1}: add reply param to format_status")
        continue
    
    # 2. Replace await Reply(...) with await reply(...)
    if "await Reply(" in stripped:
        new_line = stripped.replace("await Reply(", "await reply(")
        new_lines.append(new_line + "\n")
        changes.append(f"L{i+1}: Reply -> reply: {stripped.strip()[:50]}")
        continue
    
    # 3. Add dependency injection to matcher handlers
    # matcher_query
    if stripped == "@matcher_query.handle()":
        new_lines.append(line)
        # Read next line
        i += 1
        next_line = lines[i].rstrip("\n")
        if "async def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict()):" == next_line:
            new_lines.append(
                "async def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict(), reply: Reply = Reply):\n"
            )
            changes.append(f"L{i+1}: inject reply dep in matcher_query")
        else:
            new_lines.append(next_line + "\n")
            changes.append(f"WARNING: matcher_query handler didn't match expected sig: {next_line}")
        continue
    
    # matcher_update
    if stripped == "@matcher_update.handle()":
        new_lines.append(line)
        i += 1
        next_line = lines[i].rstrip("\n")
        if "async def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict()):" == next_line:
            new_lines.append(
                "async def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict(), reply: Reply = Reply):\n"
            )
            changes.append(f"L{i+1}: inject reply dep in matcher_update")
        else:
            new_lines.append(next_line + "\n")
        continue
    
    # matcher_hider_update
    if stripped == "@matcher_hider_update.handle()":
        new_lines.append(line)
        i += 1
        next_line = lines[i].rstrip("\n")
        if "async def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict()):" == next_line:
            new_lines.append(
                "async def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict(), reply: Reply = Reply):\n"
            )
            changes.append(f"L{i+1}: inject reply dep in matcher_hider_update")
        else:
            new_lines.append(next_line + "\n")
        continue
    
    # matcher_list
    if stripped == "@matcher_list.handle()":
        new_lines.append(line)
        i += 1
        next_line = lines[i].rstrip("\n")
        if "async def _(event: OneBotV11GroupMessageEvent):" == next_line:
            new_lines.append(
                "async def _(event: OneBotV11GroupMessageEvent, reply: Reply = Reply):\n"
            )
            changes.append(f"L{i+1}: inject reply dep in matcher_list")
        else:
            new_lines.append(next_line + "\n")
        continue
    
    new_lines.append(line)

# Handle the case where the loop modified i - we need to account for skipped lines
# Actually the for loop over enumerate(lines) doesn't let us skip, so let me redo this properly
# Let me rewrite using while loop instead
with open(path, "r") as f:
    content = f.read()

# Much simpler: string-level replacements

# 1. format_status - add reply param
old = "async def format_status(\n    label: str, kadou_data: dict, today_str: str, *,"
new = "async def format_status(\n    reply, label: str, kadou_data: dict, today_str: str, *,"
assert old in content, "format_status sig not found"
content = content.replace(old, new)

# 2. All await Reply( -> await reply(
# But NOT the module-level "Reply = locales_init(" line
# Count occurrences first
reply_calls = [m.start() for m in re.finditer(r"await Reply\(", content)]
# Filter out the module-level line (it's "Reply = locales_init(" not "await Reply(")
print(f"Found {len(reply_calls)} await Reply( calls")
content = content.replace("await Reply(", "await reply(")

# 3. format_status call sites need reply as first arg
content = content.replace("await format_status(store_name,", "await format_status(reply, store_name,")
content = content.replace('await format_status("Hider",', 'await format_status(reply, "Hider",')
content = content.replace('line = await format_status(store_name,', 'line = await format_status(reply, store_name,')
content = content.replace('"Hider", hider_kadou, today_str,', 'reply, "Hider", hider_kadou, today_str,')

# 4. Matcher handler dependency injection
content = content.replace(
    "@matcher_query.handle()\nasync def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict()):",
    "@matcher_query.handle()\nasync def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict(), reply: Reply = Reply):"
)
content = content.replace(
    "@matcher_update.handle()\nasync def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict()):",
    "@matcher_update.handle()\nasync def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict(), reply: Reply = Reply):"
)
content = content.replace(
    "@matcher_hider_update.handle()\nasync def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict()):",
    "@matcher_hider_update.handle()\nasync def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict(), reply: Reply = Reply):"
)
content = content.replace(
    "@matcher_list.handle()\nasync def _(event: OneBotV11GroupMessageEvent):",
    "@matcher_list.handle()\nasync def _(event: OneBotV11GroupMessageEvent, reply: Reply = Reply):"
)

# Verify no more await Reply( except module-level
remaining = len(re.findall(r"await Reply\(", content))
print(f"Remaining await Reply( (should be 0): {remaining}")

# Verify syntax
try:
    compile(content, path, "exec")
    print("Syntax: OK")
except SyntaxError as e:
    print(f"SYNTAX ERROR: {e}")
    sys.exit(1)

with open(path, "w") as f:
    f.write(content)
print(f"{path} written successfully")