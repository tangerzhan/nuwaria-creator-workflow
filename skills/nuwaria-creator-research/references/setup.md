# 安装与工作区

以下 `<技能目录>` 指本文件上一级的上一级，即包含 SKILL.md 的目录；所有 Python 命令使用已安装 requirements.txt 的同一解释器。首次初始化和环境检查不会发信或写 Notion。

## macOS

需要 Python 3.10+、Chrome 或 Edge、FFmpeg（必须同时有 ffmpeg 和 ffprobe）。已有 Homebrew 时可用 `brew install python ffmpeg`；没有 Homebrew 时先选择适合自己的官方安装方式，不静默安装包管理器。Chrome/Edge 从官方渠道安装。日常默认浏览器可以继续是 Safari；本自动适配器通过 CDP 连接 Chromium，不支持 Safari。Apple Silicon 和 Intel 都通过 PATH 发现工具，不固定 `/opt/homebrew` 或 `/usr/local`。

```bash
python3 -m venv "$HOME/.local/share/nuwaria-venv"
"$HOME/.local/share/nuwaria-venv/bin/python" -m pip install -r "$HOME/.agents/skills/nuwaria-creator-research/requirements.txt"
"$HOME/.local/share/nuwaria-venv/bin/python" "$HOME/.agents/skills/nuwaria-creator-research/scripts/doctor.py"
```

用独立资料目录打开 Chrome；浏览器窗口由本人完成 Instagram 登录：

```bash
open -na "Google Chrome" --args --remote-debugging-port=9222 --remote-debugging-address=127.0.0.1 --user-data-dir="$HOME/NUWARIA/chrome-profile"
```

使用 Microsoft Edge 时，把上面的应用名替换为 `Microsoft Edge`，例如：

```bash
open -na "Microsoft Edge" --args --remote-debugging-port=9222 --remote-debugging-address=127.0.0.1 --user-data-dir="$HOME/NUWARIA/edge-profile"
```

一次只启动一个研究实例占用 9222 端口。Safari-only 的人工整理范围见 workflow.md；不能声称已自动采集。

不要把调试端口开放到公网，不复制别人的浏览器资料目录。Playwright 连接这个 Chrome，不需要额外下载 Playwright 浏览器。

## Windows

使用 Python 3.10+ 创建虚拟环境并安装 requirements.txt。FFmpeg 已在 PATH 中即可；否则把包含 ffmpeg.exe 和 ffprobe.exe 的文件夹绝对路径填写到项目 `ffmpeg_bin`。

Chrome 通常在 `C:/Program Files/Google/Chrome/Application/chrome.exe`，需确认实际位置。经用户需要启动时，PowerShell 示例：

```powershell
Start-Process -WindowStyle Hidden -FilePath 'C:/Program Files/Google/Chrome/Application/chrome.exe' -ArgumentList @('--remote-debugging-port=9222', '--remote-debugging-address=127.0.0.1', "--user-data-dir=$env:USERPROFILE/NUWARIA/chrome-profile")
```

## 空白初始化

由用户指定批次日期，以下日期仅为命令示例：

```bash
python <技能目录>/scripts/setup_workspace.py --workspace <工作区绝对路径> --date 2026-10-12 --target 100
python <技能目录>/scripts/creator_workflow/workflow.py --project <工作区>/candidate_research_2026-10-12 status
```

已有同名批次时不会覆盖。首次初始化自动载入 assets/team_history.json 团队去重快照，无需作者本机路径。快照时间见 generated_at；它不是实时联系状态，继续连接团队 Notion 获取最新记录。旧工作区更新技能后运行 queue-check 或 scan 也会合并该快照。

后续批次使用 `workflow.py --project <新目录> init --date YYYY-MM-DD --target 100 --from-project <旧目录>`，继承配置和历史去重，生成空审核表。

## Notion 配置（选用）

在用户本机工作区中将 `.env.example` 复制为 `.env`，填 `NOTION_TOKEN`，并由用户把数据库/SOP 分享给对应集成。不要让用户在聊天中贴密钥。

在批次 project.json 填写自己的：

| 字段 | 用途 |
|---|---|
| notion_data_source | 达人主表的 data source ID，注意不同于数据库 ID |
| notion_sop | SOP 页面 ID |
| notion_env | 本机凭证文件绝对路径 |
| notion_tracking_data_source | 合作建联记录表 data source ID |
| notion_main_page | 建联预检读取的主页面 ID |
| notion_stats_table | 统计 table block ID，只有统计更新需要 |
| notion_stats_paragraph | 统计说明 paragraph block ID，只有统计更新需要 |

先用 `refresh-sources` 只读刷新 SOP、主表结构和历史。这会替换空白模板的 schema.json/existing.json，不创建数据库。现有适配器依赖团队中文字段和状态；不同结构先读真实 schema 并映射、测试，不能猜字段或直接写入。

`notion_tracking_data_source` 是成功合作参考来源；判断成功时要读取发布/返图证据，不能仅凭已寄出判断。

## Zoho 配置（仅外发时需要）

把 `zoho_mail.auth.example.json` 复制为同工作区的 `zoho_mail.auth.json`，在本机填账号所属地域的 accounts_url、mail_base_url、account_id、client_id、client_secret、refresh_token、from_email。不要提交凭证文件。在 project.json 填 `zoho_auth` 绝对路径及 `sender_email`，两处发件地址须相同。

工具复用已有合法 OAuth 配置，不代办 OAuth 应用或替用户授予权限。凭证、授权范围及发送配额必须由团队确认。未知配置不执行外发。

邮件历史别名写在本批 `contact_email_aliases.json`，格式为列表，每项包含 handle、current_email、previous_emails；只接受已核实的改邮证据。跨平台账号别名在 `identity_aliases.json`。

## 常见问题

- Chrome 连接失败：确认 Chrome 是带独立资料目录的调试实例，端口与 project.json 的 cdp 一致。
- 缺 FFmpeg：运行 doctor.py；把可执行程序目录加入 PATH 或填写 ffmpeg_bin，再检测。
- Notion 无权限：确认 data source ID、集成权限和本机凭证；不重复创建记录。
- 页面验证码、403、429：停止受限入口，交由用户正常处理；不绕过。
- macOS 兼容性：代码使用 pathlib 和 PATH 查找 FFmpeg；Mac 的浏览器及登录端到端流程仍需在同事机器上验证。
