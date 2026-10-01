#!/usr/bin/env python3
"""Fix: update kadou plugin to use new nonebot-plugin-locales Depends-based API."""
import re, sys

path = sys.argv[1] if len(sys.argv) > 1 else "plugins/kadou/__init__.py"

with open(path, "r") as f:
    c = f.read()

# 1. format_status: add `reply` as first param, change Reply(key,...) to reply(key,...)
#    old: async def format_status(label, kadou, today_str, prefix="", hider=False, hider_indent="")
old_fs = """async def format_status(
    label, kadou, today_str, prefix="", hider=False, hider_indent="",
):
    if not kadou:
        key = "status.not_updated"
        if hider:
            return await Reply(key, hider_indent=hider_indent)
        return await Reply(key, prefix=prefix, label=label)
    num = kadou.get("num", "?")
    display_time = kadou.get("updated_at", "")
    key = "status.updated"
    if display_time.startswith(today_str):
        display_time = display_time.split("T")[1][:5]
    if hider:
        return await Reply(key, hider_indent=hider_indent, num=num, display_time=display_time)
    return await Reply(key, prefix=prefix, label=label, num=num, display_time=display_time)"""

new_fs = """async def format_status(
    reply, label, kadou, today_str, prefix="", hider=False, hider_indent="",
):
    if not kadou:
        key = "status.not_updated"
        if hider:
            return await reply(key, hider_indent=hider_indent)
        return await reply(key, prefix=prefix, label=label)
    num = kadou.get("num", "?")
    display_time = kadou.get("updated_at", "")
    key = "status.updated"
    if display_time.startswith(today_str):
        display_time = display_time.split("T")[1][:5]
    if hider:
        return await reply(key, hider_indent=hider_indent, num=num, display_time=display_time)
    return await reply(key, prefix=prefix, label=label, num=num, display_time=display_time)"""

assert old_fs in c, "format_status not found!"
c = c.replace(old_fs, new_fs)
print("1/4 format_status fixed")

# 2. matcher_query: inject reply, pass to format_status
old_mq = """@matcher_query.handle()
async def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict()):
    name = args.get("name", "")
    ctx = get_store_context(event, name, is_hider=False)
    if not ctx:
        return

    store_info = ctx["store_info"]
    store_kadou = ctx["kadou"][ctx["store_id"]]
    today_str = now_local().date().isoformat()
    store_name = store_info.get("name", name)

    manifest = load_json(data_dir / "manifest.json")
    data_id = manifest.get(str(event.group_id), "")
    prefix_text = await Reply("status.prefix", city_id=data_id) if data_id else ''
    msg = await format_status(store_name, store_kadou, today_str, prefix=prefix_text)

    # Hider 数据（仅当群有 hider 权限时显示）
    hider_ctx = get_store_context(event, name, is_hider=True)
    if hider_ctx:
        hider_kadou = hider_ctx["kadou"][hider_ctx["store_id"]]
        hider_msg = await format_status("Hider", hider_kadou, today_str, hider=True, hider_indent=" "*4)
        msg += f"\\n{hider_msg}"

    await matcher_query.finish(msg)"""

new_mq = """@matcher_query.handle()
async def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict(), reply: Reply = Reply):
    name = args.get("name", "")
    ctx = get_store_context(event, name, is_hider=False)
    if not ctx:
        return

    store_info = ctx["store_info"]
    store_kadou = ctx["kadou"][ctx["store_id"]]
    today_str = now_local().date().isoformat()
    store_name = store_info.get("name", name)

    manifest = load_json(data_dir / "manifest.json")
    data_id = manifest.get(str(event.group_id), "")
    prefix_text = await reply("status.prefix", city_id=data_id) if data_id else ''
    msg = await format_status(reply, store_name, store_kadou, today_str, prefix=prefix_text)

    # Hider 数据（仅当群有 hider 权限时显示）
    hider_ctx = get_store_context(event, name, is_hider=True)
    if hider_ctx:
        hider_kadou = hider_ctx["kadou"][hider_ctx["store_id"]]
        hider_msg = await format_status(reply, "Hider", hider_kadou, today_str, hider=True, hider_indent=" "*4)
        msg += f"\\n{hider_msg}"

    await matcher_query.finish(msg)"""

assert old_mq in c, "matcher_query not found!"
c = c.replace(old_mq, new_mq)
print("2/4 matcher_query fixed")

# 3. matcher_update: inject reply, use reply() instead of Reply()
old_mu = """@matcher_update.handle()
async def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict()):
    name = args.get("name", "")
    sign = args.get("sign")
    num_str = args.get("num", "0")
    try:
        delta = int(num_str)
    except ValueError:
        return
    if sign == "-":
        delta = -delta

    ctx = get_store_context(event, name, is_hider=False)
    if not ctx:
        return

    store_info = ctx["store_info"]
    store_id = ctx["store_id"]
    store_kadou = ctx["kadou"]
    store_data = store_kadou.get(store_id)
    if not store_data:
        return

    old_num = store_data.get("num", 0)
    new_num = old_num + delta
    if new_num < 0:
        await matcher_update.finish(await Reply("errors.num_less_than_zero"))

    store_data["num"] = new_num
    store_data["updated_at"] = now_local().isoformat()
    save_json(data_dir / f"{ctx['file_path'].name}", store_kadou)

    # 同步更新 Hider 数据
    store_kadou_hider = load_json(data_dir / "hider_" / f"{ctx['file_path'].name}") if not ctx["is_hider_mode"] and ctx["has_hider"] else None
    if store_kadou_hider and store_id in store_kadou_hider:
        store_kadou_hider[store_id]["num"] = new_num
        store_kadou_hider[store_id]["updated_at"] = now_local().isoformat()
        save_json(data_dir / "hider_" / f"{ctx['file_path'].name}", store_kadou_hider)

    store_name = store_info.get("name", name)
    await matcher_update.finish(await Reply("update.success", store_name=store_name, new_num=new_num))"""

# Wait, let me check what the actual matcher_update code looks like
old_mu = """    await matcher_update.finish(await Reply("errors.num_less_than_zero"))"""

new_mu = """    await matcher_update.finish(await reply("errors.num_less_than_zero"))"""
assert old_mu in c, "matcher_update err not found!"
c = c.replace(old_mu, new_mu)
print("3a matcher_update err fixed")

old_mu2 = """    await matcher_update.finish(await Reply("update.success", store_name=store_name, new_num=new_num))"""
new_mu2 = """    await matcher_update.finish(await reply("update.success", store_name=store_name, new_num=new_num))"""
assert old_mu2 in c, "matcher_update success not found!"
c = c.replace(old_mu2, new_mu2)
print("3b matcher_update success fixed")

# Add reply dependency to matcher_update handler
old_mu_def = """@matcher_update.handle()
async def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict()):"""
new_mu_def = """@matcher_update.handle()
async def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict(), reply: Reply = Reply):"""
assert old_mu_def in c, "matcher_update def not found!"
c = c.replace(old_mu_def, new_mu_def)
print("3c matcher_update dep injected")

print("3/4 matcher_update fixed")

# 4. Fix matcher_hider_update
old_mhu_err = """await matcher_hider_update.finish(await Reply("errors.num_less_than_zero"))"""
new_mhu_err = """await matcher_hider_update.finish(await reply("errors.num_less_than_zero"))"""
assert old_mhu_err in c, "matcher_hider_update err not found!"
c = c.replace(old_mhu_err, new_mhu_err)
print("4a matcher_hider_update err fixed")

old_mhu_success = """await matcher_hider_update.finish(await Reply("update.hider_success", store_name=store_name, new_num=new_num))"""
new_mhu_success = """await matcher_hider_update.finish(await reply("update.hider_success", store_name=store_name, new_num=new_num))"""
assert old_mhu_success in c, "matcher_hider_update success not found!"
c = c.replace(old_mhu_success, new_mhu_success)
print("4b matcher_hider_update success fixed")

old_mhu_def = """@matcher_hider_update.handle()
async def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict()):"""
new_mhu_def = """@matcher_hider_update.handle()
async def _(event: OneBotV11GroupMessageEvent, args: dict = RegexDict(), reply: Reply = Reply):"""
assert old_mhu_def in c, "matcher_hider_update def not found!"
c = c.replace(old_mhu_def, new_mhu_def)
print("4c matcher_hider_update dep injected")

print("4/4 matcher_hider_update fixed")

# 5. matcher_list: inject reply
old_ml_def = """@matcher_list.handle()
async def _(event: OneBotV11GroupMessageEvent):"""
new_ml_def = """@matcher_list.handle()
async def _(event: OneBotV11GroupMessageEvent, reply: Reply = Reply):"""
assert old_ml_def in c, "matcher_list def not found!"
c = c.replace(old_ml_def, new_ml_def)
print("5/5 matcher_list dep injected")

# Fix matcher_list body - Reply -> reply
old_ml_prefix = """        prefix_text = await Reply("status.prefix", city_id=data_id) if data_id else ''"""
new_ml_prefix = """        prefix_text = await reply("status.prefix", city_id=data_id) if data_id else ''"""
assert old_ml_prefix in c, "matcher_list prefix not found!"
c = c.replace(old_ml_prefix, new_ml_prefix)
print("5b matcher_list prefix fixed")

old_ml_line = """        line = await format_status(store_name, store_kadou, today_str, prefix=prefix_text)"""
new_ml_line = """        line = await format_status(reply, store_name, store_kadou, today_str, prefix=prefix_text)"""
assert old_ml_line in c, "matcher_list line not found!"
c = c.replace(old_ml_line, new_ml_line)
print("5c matcher_list line fixed")

old_ml_hider = """        hider_line = await format_status(
            "Hider", hider_kadou, today_str, hider=True, hider_indent=" "*4"""
new_ml_hider = """        hider_line = await format_status(
            reply, "Hider", hider_kadou, today_str, hider=True, hider_indent=" "*4"""
assert old_ml_hider in c, "matcher_list hider not found!"
c = c.replace(old_ml_hider, new_ml_hider)
print("5d matcher_list hider fixed")

print("Done! All Reply() calls replaced with reply()")

# Verify syntax
try:
    compile(c, path, "exec")
    print("Syntax: OK")
except SyntaxError as e:
    print(f"Syntax error: {e}")
    sys.exit(1)

with open(path, "w") as f:
    f.write(c)
print(f"{path} written")