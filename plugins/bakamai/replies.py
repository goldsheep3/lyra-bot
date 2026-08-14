REPLY_DICT = {
    "add_success": "[Bakamai] 已将 {name} 添加到白名单，ENTRY！",
    "add_fail_uuid": "[Bakamai] 果咩，{name} 没找到 UUID 记录……",
    "add_error": "[Bakamai] 服务器好像似了喵（）请检查服务器状态！",
    "remove_success": "[Bakamai] 已经把 {name} 从档案中抹除掉了喵，同步完成！",
    "status_empty": "[Bakamai] 服务器在线人数：\n{server_name}：0人（更新于 现在）",
    "status_header": "[Bakamai] 服务器在线人数：\n{server_name}：{current}/{max}人（更新于 现在）",
    "status_player_bound": "• {name} ({nick})",
    "status_player_unbound": "• {name} (未绑定)",
    "status_error": "[Bakamai] 服务器在线人数：\n{server_name}：?人（请检查服务器状态）",
    "conflicted_group": "[Bakamai] 群配置冲突！请检查群实例绑定状态是否重复。",
    "not_admin": "[Bakamai] 只有管理员或群主可以为其他人操作白名单哦！"
}

def say(key: str, **kwargs) -> str:
    fmt = REPLY_DICT.get(key, f"〔Error: {key}〕")
    return fmt.format(**kwargs)
