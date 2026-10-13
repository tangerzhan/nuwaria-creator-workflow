# 建联与 Notion 同步

仅在用户明确要求发信、回信或同步时执行。安装技能、研究名单、上传 GitHub 不构成邮件授权。旧项目授权不自动延续；同一次已授权发送完成后继续同步并回读。

## 前置

- 按 setup.md 配自己的 Notion/Zoho。两张表的中文字段须与适配器匹配；工具不创建数据库，也不含真实模板快照。
- 当前 Notion SOP 是文案来源。工具仍为 NUWARIA 定制，build 从 SOP 模板章节提取品牌尾段；结构不同先适配测试，不直接发信。
- Python 不可用 `-O`，否则 assert 检查会关闭。
- 同一批次由一个负责人发送，没有跨机器事务锁；实时查重不保证两人同时发送时互斥。

## 首次邀约

通过 workflow.py --project 执行。先读具体 action 需要的 JSON 字段和当前 SOP，再准备可审阅内容。

1. outreach preflight 实时读 Notion 和 Zoho 已发送；按账号、正式别名、完整邮箱查重，不按邮箱用户名片段合并。
2. 在 outreach/personalization.json 保存实际观察、称呼与 evidence indices。分批发送用 batch_scope.json 的 handles / authorized_count 限定本次授权范围。
3. outreach build 生成 drafts.json，审阅收件人、观察、条款与发布形式，再 outreach approve-review 记录正文摘要。审阅记录不替代用户授权。
4. outreach send --limit N，N 不超过用户授权；例如本次 40 封就只发送 40 封，下一波等待用户新授权。
5. outreach reconcile 回查 message ID、正文和投递情况。不确定、超时或中断先 reconcile，不直接重发。
6. 根据现有导入状态执行 outreach build-import、审阅方案、outreach import-notion 或 outreach sync-sent，随后 outreach verify-pages 回读。不回退最新回复/人工状态，不重复建档。
7. 配好统计块后 outreach stats，再 outreach export-progress。没有配置或失败必须说明，不能声称已同步。

导入与同步会校验方案审阅摘要，按实际 action 实现准备审阅文件，不能为了通过检查盲写 approved。

## 回信与来信记录

- replies --folder <审阅目录> prepare|send|verify|sync：先刷新往来，逐人 reply_scope，审阅 reply_plan 后记录 reply_review，回读成功再同步。
- mail-sync --folder <审阅目录> collect|prepare|apply|verify：已审阅来信同步，不发送；包括无需回信、暂缓回复、已收件/发布、佣金确认，不只更新本次发出的邮件。
- closeout：只在明确终止时使用，保留历史与报价，不把退信当达人回复。

## 业务状态

已发信表示首次邀请后尚无回复；已暂停表示有实质回复且本轮明确终止，两者不并存。已报价是历史事实，可与当前行动阶段并存；其他阶段互斥。只说要收费但还没报价，不算已报价。

寄样进度以建联表真实字段为准，不用联系标签推断。合作选项、产品名及必要尺寸、联系人、收件人分别记录，不写内部 variant ID。佣金区分未提出、待回应、明确同意/拒绝，同意产品合作不等于同意佣金。

产品规格、物流、费用、赠品和形式按当前团队确认，不复制作者过去个案承诺。收件地址等私人信息留在授权工作区/Notion，不进入代码仓库。

## 测试边界

迁移版保留草稿审阅、查重和回读保护；数据库 ID、发件人、OAuth 和别名改成本地配置。发布时只做离线测试，不给真实达人发送测试邮件。同事首次接入自己的表结构，先只读核验和审阅方案，再执行授权写入。
