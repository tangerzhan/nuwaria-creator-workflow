# 研究流程

目标为 NUWARIA 找到可自然分享饰品、随身香气或包挂的个人生活创作者。强调温柔克制、天然手作质感；不以族裔判断品牌气质。用户当前要求优先于默认值。

## 判断顺序

1. 确定日期、人数、工作区、团队去重来源及最新物流范围。不要把作者历史物流名单写死为团队规则。
2. 每轮发现约 20–30 条有原帖或公开简介依据的线索，用内容和生活场景关键词，不强加国家关键词。已成功合作的真实返图/发布者可作为相似创作者的起点。
3. queue-check / scan 先查当前和历史名单、别名、完整邮箱以及历史初筛。旧 hold/exclude 不反复访问；有新证据时在当前 screening.json 写 pass 和重查理由。
4. screen 每组约 6 人，实际打开 quick_screen.jpg；生成下一张会覆盖，必须先看完。先判断主线、明显冲突、画面和粗略分数。
5. 通过者再核实最近 12 条，实际看图并结合文案确认至少 4 条独立自然场景。争议处补细节帧/全部轮播。抽帧不等于完整播放。
6. 沿官方简介→个人网站/Linktree→Contact/About/Email 找公开邮箱。不猜邮箱，不把服务商客服邮箱当达人邮箱。核查已发现的自营店和关联平台。
7. 手工写审核与有依据的评分，merge-reviews 校验合并。每约 30 条记录来源、新账号、通过数；重复密集且低产时更换入口。持续推进到用户目标。
8. check --complete 后 export；未达目标只能 export --draft，明确已复核人数，不把候选池当正式名单。

## 默认筛选标准

- 主平台 1000–100000 粉；官方关联副平台已知超上限排除，未知不阻塞；同一人只计一次。
- 最近 30 天内有公开图文或视频；最近 12 条按时间排序，置顶老帖不能替代最近内容。
- 主线是个人日常、生活分享、个人选物。健身、户外、宠物、阅读/书评、手账、纯穿搭、教程主导者排除；少量兴趣不自动排除。
- 四条依据为本人佩戴、使用、携带、包内物、赠礼等。只有咖啡、景物、家居或温柔色调不够。同一事件、同套穿搭反复发布不重复计数。
- 配饰与香气是可替代方向，不要求同时存在。天然材质和随身使用习惯是正面依据。
- 自有首饰/同类香气店或商店账号排除；第三方联盟链接不是自营店。其他行业创业不自动排除。排他、报价、接受置换及受众均须真实证据。
- 核实公开邮箱；未知收件地标待确认。仅按实际物流能力排除，不按姓名语言族裔推断。

## 评分

| 键 | 权重 |
|---|---:|
| natural_seeding | 25 |
| brand_fit | 20 |
| conversion | 20 |
| audience | 15 |
| performance | 10 |
| commercial | 5 |
| risk_quality | 5 |

每维 0–5，提供 reason；加权分 = rating/5×权重。默认自然植入+品牌适配至少 27/45 进入复核，不替代其他门槛。资料缺失不写 0 或中间分，不把内容分折算为 100 分。B 级只表示内容复核结论。

## 命令

所有命令加前缀 `python <技能目录>/scripts/creator_workflow/workflow.py --project <批次绝对路径>`。使用虚拟环境解释器；技能不改变 Codex 审批权限。

| 命令 | 用途 |
|---|---|
| status | 当前正式人数与待审情况 |
| refresh-sources | 只读刷新已配置 Notion SOP、schema 和历史 |
| queue-check queue.json | 本地预查队列 |
| scan queue.json | 主页元数据及截图，不是深度审核 |
| screen h1 h2 | 初筛图，必须实际看 |
| browse URL1 URL2 | 原生只读发现，查看截图/原帖后人工选择 |
| digest h1 h2 | 简介、文案与外链线索 |
| media-capture h1 | 捕获 Instagram 原生公开媒体 |
| media-render h1 | 下载/抽帧，等完成再生成 board |
| board h1 | post_audits/h1/overview.jpg，实际查看 |
| media-detail h1:2,6 | 选定视频补 12 点抽帧 |
| media-carousel h1:4,12 | 补看轮播全部图片；视频页只是缩略图 |
| links h1 / browser-links h1 | 官方外链；HTTP 406 可普通浏览器读取 |
| source-links URL / browser-links URL | 官方联系页；403/429/验证停止该处 |
| comments h1:1,4 / read-comments h1:1,4 | 按需评论抽查，不凭空推断购买意向 |
| network queue-next.json h1 | 从已读评论扩散，仍需初筛 |
| tiktok handle | 基本资料，不冒充 TikTok 12 条核验 |
| merge-reviews batch.json | 输入路径相对当前终端目录，验证合并 |
| check --complete / export | 满额校验导出；未满额 export --draft |

队列文件路径相对批次目录：

```json
[{"handle":"example_creator","url":"https://www.instagram.com/example_creator/","source":"原帖链接","discovery_attributes":"已读内容依据","discovery_reason":"进入初筛理由"}]
```

screening.json 保存 `{"example_creator":{"verdict":"pass","reason":"实际概览依据和初评分"}}`，hold/exclude 也保留原因。

人工复核 batch.json 结构示例，不能直接作为真实证据导入：

```json
{
  "example_creator": {
    "verdict": "include", "level": "B", "person_key": "example_creator",
    "aliases": [], "visual_review_completed": true,
    "public_email": "creator@example.com", "public_email_source": "官方来源链接",
    "location": "未确认", "rationale": "品牌适配依据",
    "scenes": {"1":"具体场景","3":"具体场景","6":"具体场景","9":"具体场景"},
    "ordinary_exclude": [], "comment_indices": [],
    "comments_note": "未专项抽查，购买意向未知",
    "business": "已核实范围", "risks": "未核事项",
    "product": "具体类型及理由", "contact_status": "未联系"
  }
}
```

scores.json 对应账号保存 `{"natural_seeding":{"rating":3,"reason":"依据"},"brand_fit":{"rating":3,"reason":"依据"}}`。已核实副平台可在 review 的 linked_accounts 列表写 platform、url、followers、checked_at。

正式主表、评分、来源、元数据、去重索引和发送日志必须保留。只有用户许可且实际审阅后的图片才可删除，设置 allow_reviewed_image_deletion 和逐人 visual_review_completed；不能用删除许可跳过查看。

## Safari / 人工模式

本版自动采集仅支持通过 CDP 连接 Chromium 浏览器。Safari 可用于人工查找和查看，但不能直接运行 scan/browse/媒体捕获。用户可提供公开链接、实际审阅记录和截图，Codex据此整理初筛池、评分与待核项。未得到完整 12 条真实证据者不计正式完成。现有自动导出验证要求结构化 profile/audit；人工模式先交付清楚标注范围的表格，不伪造自动采集记录来绕过校验。
