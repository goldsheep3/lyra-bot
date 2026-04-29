# lyra-bot

基于 **Nonebot2** 框架开发的 QQ机器人。

## 快速使用

1. 设置服务器基础时区为 Asia/Shanghai：`sudo timedatectl set-timezone Asia/Shanghai`

2. 安装 Python (3.12+), uv （或其他 Python 管理器）

3. 使用 `uv sync` 安装虚拟环境

4. 使用 `uv tool install nb-cli` 安装 nonebot2 脚手架

5. 设置开机自启：`sudo vim /etc/systemd/system/lyra-bot.service`

```toml
[Unit]
Description=Lyra Bot Service
After=network.target

[Service]
Type=simple
User={youruser}
Group={youruser}
WorkingDirectory=/home/{youruser}/lyra-bot
# 虚拟环境下修改为虚拟环境路径
ExecStart=/home/{youruser}/.local/bin/nb run
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

随后：
- `sudo systemctl daemon-reload`


## 🧩 插件：maib

`maib` 是一个专为 maimai DX 玩家设计的成绩查询与数据展示插件。

### 🎨 资源说明

本插件使用了以下字体以保证视觉呈现效果：

- **MiSans**: 用于主要文本内容的显示，提供极致的阅读体验。
- **JetBrainsMono**: 作为等宽字体，用于版本数字及达成率（Achievement）数字显示。
- **NotoColorEmoji**: 用于显示 emoji 。
- **NotoSansSymbols2**: 用于显示特殊符号（【✦】）。

### 🤝 致谢与参考

本项目的实现离不开以下优秀项目及数据的支持：

- **查分器接口**:
  - [水鱼 diving-fish 查分器](https://www.diving-fish.com/maimaidx/prober) 提供 QQ 号查询游玩数据，国服定数、版本信息，拟合定数等信息
- **谱面数据**:
  - [Neskol/Maichart-Converts](https://github.com/Neskol/Maichart-Converts) 提供谱面转换
  - [AstroDX 下载站 (MilkBot))](https://astrodx.milkbot.cn) (似乎是)整理转换后谱面
- **别名库**:
  - [落雪查分器](https://maimai.lxns.net)
  - [Yuzuchan 别名库](https://www.yuzuchan.moe/api/maimaidx/maimaidxalia) `api`
