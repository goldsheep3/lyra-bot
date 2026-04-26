# lyra-plugin-help
from nonebot import on_regex

_help = on_regex(r"^(帮助|help)\s*(maib|舞萌|mai|maimai)$", priority=10, block=True)


@_help.handle()
async def _():
    await _help.finish("""
LyraHELP | maib (小梨音游核心)

1. 下载谱面
   下载指定的谱面（下载谱面 11951）
   不带 ID 回复小梨的唯一谱面 INFO 消息也可以下载回复消息中的谱面
2. xxx是什么歌
   通过曲名/别名查询歌曲，可以在后面带“？”强制模糊搜索
3. idxxx/infoxxx
   通过id查询谱面信息
4. b50
   查询 b50，默认获取国服数据
   可在后面@他人或直接输入qq号查询指定玩家数据
   可在后面带 jp 获取日服数据（如果已经从lyra-sync获取数据）
5. ra
   计算 DXRating，参数为 ra <定数> <完成率>
   完成率可以使用“鸟家”“sss+”等表达方式
6. 【lyra-sync】私聊发送 JSON 文件
   (测试中 / Beta)
   通过 lyra-sync 获取 JSON 后，私聊发送进行解析
7. 【lyra-sync】私聊发送 获取code
   (测试中 / Beta)
   获取 lyra-sync 的同步 code

""".strip())