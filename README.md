# lyra-bot

基于 **Nonebot2** 框架开发的 QQ机器人。

## 快速使用（使用 uv）

1. 设置服务器基础时区为 Asia/Shanghai：`sudo timedatectl set-timezone Asia/Shanghai`

2. 在用户环境下[安装 uv](https://uv.doczh.com/getting-started/installation/)

3. 使用 `uv sync --python 3.12` 安装虚拟环境

4. 使用 `uv tool install nb-cli` 安装 nonebot2 脚手架

5. 设置用户级服务
  - `vim ~/.config/systemd/user/lyra.service`
  - 或 `nano ~/.config/systemd/user/lyra.service`

```toml
[Unit]
Description=Lyra Bot Service
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/lyra-bot
ExecStart=%h/.local/bin/uvx --from nb-cli nb run
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

6. 检查并启用开机自启：
  - `systemctl --user daemon-reload`
  - `systemctl --user enable --now lyra.service`

7. 允许服务自行运行：
  - `sudo loginctl enable-linger`
