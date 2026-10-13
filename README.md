# NUWARIA 达人工作流

把 Instagram/TikTok 达人发现、初筛、12 条内容复核、评分、Excel 导出，以及已授权的 Zoho 建联和 Notion 同步交给 Codex 协作完成。包含自足的 Codex skill 和 Python 工具；适用 Windows / macOS。macOS 路径和可执行文件已适配，但发布前未在真实 Mac 上运行浏览器流程。

**没有 GitHub 账号也能安装：**由有私有仓库权限的同事下载 ZIP 转发，解压后按下面步骤操作。安装包包含团队历史去重索引（账号、别名、公开联系邮箱、人物标识和初筛结论），不包含凭证、收件地址、邮件正文或浏览器登录状态。仅在授权团队内分享。

## 安装给同事

有仓库权限者可以克隆 `https://github.com/tangerzhan/nuwaria-creator-workflow.git`，或在 GitHub 点 Code → Download ZIP。没有账号者使用团队发来的 ZIP。

在解压后的目录打开终端。macOS：

```bash
python3 install.py
python3 -m venv "$HOME/.local/share/nuwaria-venv"
"$HOME/.local/share/nuwaria-venv/bin/python" -m pip install -r requirements.txt
```

Windows PowerShell：

```powershell
python install.py
python -m venv "$env:USERPROFILE/.local/share/nuwaria-venv"
& "$env:USERPROFILE/.local/share/nuwaria-venv/Scripts/python.exe" -m pip install -r requirements.txt
```

安装器将完整技能复制到 `~/.agents/skills/nuwaria-creator-research`；已经存在时停止，避免覆盖同事修改。更新时先保留旧技能再安装新版，研究数据留在独立工作区。

打开 Codex，说：

> 使用 $nuwaria-creator-research，先检查我的环境并初始化达人工作区。我的 Python 虚拟环境在 ~/.local/share/nuwaria-venv。先配置团队历史去重来源，再开始研究；暂不发邮件。

若技能未出现，重启 Codex。也可以向 `$skill-installer` 提供仓库中 `skills/nuwaria-creator-research` 的地址；私有仓库仍需 GitHub 访问权限。技能目录和支持资源的组织方式参考 [OpenAI 官方说明](https://learn.chatgpt.com/docs/build-skills)。

## 首次配置

按技能内 [环境配置](skills/nuwaria-creator-research/references/setup.md) 完成 Python 3.10+、Chrome 或 Edge、FFmpeg；自动采集使用独立调试资料目录，由本人登录 Instagram。平时使用 Safari 不受影响；只用 Safari 时可人工查找与提供审核材料，但不能直接运行现有自动截图/采集适配器。依赖安装不等于平台已登录。

研究、导出可在本地运行；Notion 和 Zoho 按需配置。已有团队应连接同一历史数据源并分配不同批次，避免多人同时联系同一达人。仓库不提供跨机器发送锁，外发前须刷新 Notion 和已发送记录，由一个负责人执行同一批次发送。

- [研究流程、证据和评分](skills/nuwaria-creator-research/references/workflow.md)
- [建联、回信和 Notion 同步](skills/nuwaria-creator-research/references/outreach.md)

工具会保存审核元数据、原帖链接、图片和日志，但是否符合品牌、图片是否真看过仍需 Codex/人工判断。遇平台验证码或限流停止该处访问，不绕过。

## 开发验证

```bash
python -m unittest discover -s tests -v
```

测试使用临时目录，不访问真实 Notion、Zoho 或达人页面。发布目录包含最小团队去重快照；禁止把整个原工作区提交到 GitHub。

## 团队去重快照

`skills/nuwaria-creator-research/assets/team_history.json` 随安装分发，新工作区自动载入；已有工作区使用新版技能运行 `queue-check` 或 `scan` 时也会合并。快照含本地历史正式名单、当前未完成批次已入选者，以及旧 hold/exclude 初筛记录。旧初筛可凭新证据在本批标记 pass 后重查；已入选账号、别名和完整邮箱仍拦截。

这是导出时的快照，不会实时同步同事的新名单或联系状态。新增结果后由负责人更新快照并提交，团队更新技能；外发前仍查最新 Notion/Zoho。负责人导出命令：

```bash
python skills/nuwaria-creator-research/scripts/export_team_history.py --project <含完整历史索引的当前批次> --output skills/nuwaria-creator-research/assets/team_history.json
```
