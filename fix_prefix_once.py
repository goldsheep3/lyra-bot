#!/usr/bin/env python3
"""Move prefix_text outside loop, add newline between prefix and content."""
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "plugins/kadou/__init__.py"

with open(path, "r") as f:
    c = f.read()

old = """    today_str = now_local().date().isoformat()
    HIDER_INDENT = " "*4
    messages = []

    for name_key, store_info in info.items():
        store_id = str(store_info.get("id"))
        store_name = store_info.get("name", name_key)

        store_kadou = kadou.get(store_id, {"num": 0, "time": ""})
        prefix_text = await reply("status.prefix", city_id=data_id) if data_id else ''
        line = await format_status(reply, store_name, store_kadou, today_str, prefix=prefix_text)

        # Hider"""  # stop here, use the full match

new = """    today_str = now_local().date().isoformat()
    HIDER_INDENT = " "*4
    prefix_text = await reply("status.prefix", city_id=data_id) if data_id else ''
    messages = []

    for name_key, store_info in info.items():
        store_id = str(store_info.get("id"))
        store_name = store_info.get("name", name_key)

        store_kadou = kadou.get(store_id, {"num": 0, "time": ""})
        line = await format_status(reply, store_name, store_kadou, today_str)

        # Hider"""

assert old in c, "old pattern not found!"
c = c.replace(old, new)

# Also fix the final output part
old_end = """    if messages:
        await matcher_list.finish("\\n".join(messages))"""

new_end = """    if messages:
        output = "\\n".join(messages)
        if prefix_text:
            output = prefix_text + "\\n" + output
        await matcher_list.finish(output)"""

assert old_end in c, "old_end not found!"
c = c.replace(old_end, new_end)

try:
    compile(c, path, "exec")
    print("Syntax: OK")
except SyntaxError as e:
    print(f"Syntax error: {e}")
    sys.exit(1)

with open(path, "w") as f:
    f.write(c)
print(f"{path} written successfully")