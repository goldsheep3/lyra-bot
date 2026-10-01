#!/usr/bin/env python3
"""Patch plugins/kadou/__init__.py with prefix + hider_indent + /j hider."""
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "plugins/kadou/__init__.py"

with open(path, "r") as f:
    content = f.read()

# 1. format_status
old_fs = '''async def format_status(
    label: str, kadou_data: dict, today_str: str, *, hider: bool = False
) -> str:
    """Format a localized status message."""
    time_str = kadou_data.get("time", "")

    if time_str[:10] != today_str:
        key = "status.hider.not_updated" if hider else "status.common.not_updated"
        return await Reply(key, prefix="", label=label)

    num = kadou_data.get("num", 0)
    display_time = time_str[11:] if len(time_str) > 10 else time_str
    key = "status.hider.updated" if hider else "status.common.updated"
    return await Reply(
        key, prefix="", label=label, num=num, display_time=display_time
    )'''

new_fs = '''async def format_status(
    label: str, kadou_data: dict, today_str: str, *,
    prefix: str = "",
    hider: bool = False,
    hider_indent: str = "",
) -> str:
    """Format a localized status message."""
    time_str = kadou_data.get("time", "")

    if time_str[:10] != today_str:
        key = "status.hider.not_updated" if hider else "status.common.not_updated"
        if hider:
            return await Reply(key, hider_indent=hider_indent)
        return await Reply(key, prefix=prefix, label=label)

    num = kadou_data.get("num", 0)
    display_time = time_str[11:] if len(time_str) > 10 else time_str
    key = "status.hider.updated" if hider else "status.common.updated"
    if hider:
        return await Reply(key, hider_indent=hider_indent, num=num, display_time=display_time)
    return await Reply(key, prefix=prefix, label=label, num=num, display_time=display_time)'''

assert old_fs in content, "format_status not found!"
content = content.replace(old_fs, new_fs)
print("1/3 format_status ✔")

# 2. matcher_query
old_mq = '''@matcher_query.handle()
async def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict()):
    name = args.get("name", "")
    ctx = get_store_context(event, name, is_hider=False)
    if not ctx:
        return

    store_info = ctx["store_info"]
    store_kadou = ctx["kadou"][ctx["store_id"]]
    today_str = now_local().date().isoformat()

    # 普通数据
    store_name = store_info.get("name", name)
    msg = await format_status(store_name, store_kadou, today_str)

    # Hider 数据
    hider_ctx = get_store_context(event, name, is_hider=True)
    if hider_ctx:
        hider_kadou = hider_ctx["kadou"][hider_ctx["store_id"]]
        hider_msg = await format_status("Hider", hider_kadou, today_str, hider=True)
        msg += f"\\n{hider_msg}"

    await matcher_query.finish(msg)'''

new_mq = '''@matcher_query.handle()
async def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict()):
    name = args.get("name", "")
    ctx = get_store_context(event, name, is_hider=False)
    if not ctx:
        return

    store_info = ctx["store_info"]
    store_kadou = ctx["kadou"][ctx["store_id"]]
    today_str = now_local().date().isoformat()
    store_name = store_info.get("name", name)

    prefix_text = await Reply("status.prefix", city_id=name)
    msg = await format_status(store_name, store_kadou, today_str, prefix=prefix_text)

    # Hider 数据（仅当群有 hider 权限时显示）
    hider_ctx = get_store_context(event, name, is_hider=True)
    if hider_ctx:
        hider_kadou = hider_ctx["kadou"][hider_ctx["store_id"]]
        hider_msg = await format_status("Hider", hider_kadou, today_str, hider=True, hider_indent=" "*4)
        msg += f"\\n{hider_msg}"

    await matcher_query.finish(msg)'''

assert old_mq in content, "matcher_query not found!"
content = content.replace(old_mq, new_mq)
print("2/3 matcher_query ✔")

# 3. matcher_list
old_ml = '''@matcher_list.handle()
async def _(event: OneBotV11GroupMessageEvent):
    manifest = load_json(data_dir / "manifest.json")
    data_id = manifest.get(str(event.group_id))
    if not data_id:
        return

    file_path = data_dir / f"{data_id}.json"
    data = load_json(file_path)

    info = data.get("info", {})
    kadou = data.get("kadou", {})

    if not info:
        return

    today_str = now_local().date().isoformat()
    messages = []

    for name_key, store_info in info.items():
        store_id = str(store_info.get("id"))
        store_name = store_info.get("name", name_key)

        store_kadou = kadou.get(store_id, {"num": 0, "time": ""})
        messages.append(await format_status(store_name, store_kadou, today_str))

    if messages:
        await matcher_list.finish("\\n".join(messages))'''

new_ml = '''@matcher_list.handle()
async def _(event: OneBotV11GroupMessageEvent):
    manifest = load_json(data_dir / "manifest.json")
    data_id = manifest.get(str(event.group_id))
    if not data_id:
        return

    file_path = data_dir / f"{data_id}.json"
    data = load_json(file_path)

    info = data.get("info", {})
    kadou = data.get("kadou", {})

    if not info:
        return

    today_str = now_local().date().isoformat()
    HIDER_INDENT = " "*4
    messages = []

    for name_key, store_info in info.items():
        store_id = str(store_info.get("id"))
        store_name = store_info.get("name", name_key)

        store_kadou = kadou.get(store_id, {"num": 0, "time": ""})
        prefix_text = await Reply("status.prefix", city_id=name_key)
        line = await format_status(store_name, store_kadou, today_str, prefix=prefix_text)

        # Hider（仅当群有 hider 权限时显示）
        hider_ctx = get_store_context(event, name_key, is_hider=True)
        if hider_ctx:
            hider_kadou = hider_ctx["kadou"][hider_ctx["store_id"]]
            hider_line = await format_status(
                "Hider", hider_kadou, today_str,
                hider=True, hider_indent=HIDER_INDENT,
            )
            line += f"\\n{hider_line}"

        messages.append(line)

    if messages:
        await matcher_list.finish("\\n".join(messages))'''

assert old_ml in content, "matcher_list not found!"
content = content.replace(old_ml, new_ml)
print("3/3 matcher_list ✔")

with open(path, "w") as f:
    f.write(content)
print(f"\n{path} 已写入 ✓")