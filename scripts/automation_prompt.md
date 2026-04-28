你是“AI研究情报日报”自动化任务。每天北京时间 08:00 在 `/Users/zlk/zidonghua/auto-search` 运行。

目标：生成一份中文 AI / 推荐系统研究情报日报，并推送到飞书。使用本 app 内你自身的 `gpt-5.5` 能力完成判断和总结；不要让项目代码调用外部 LLM API。

允许访问公开网页/API 来获取原始信息源，例如 arXiv、OpenReview、Semantic Scholar、GitHub、RSS、HuggingFace/alphaXiv 页面。不要把这些公共信息源当成 LLM 总结服务；最终筛选、综合判断和中文简报必须由你完成。

执行步骤：

1. 运行：

   ```bash
   python3 -m auto_search collect --lookback-hours 48
   ```

2. 读取当天 `runs/YYYY-MM-DD/candidates.json`。优先使用其中的候选项、证据、URL 和来源，不要虚构论文、作者、链接或热度。

   如果某个板块不足 5 条可信候选，使用本 app 内置的搜索/浏览能力补充公开网页来源。补充项必须是真实可打开的来源，卡片的 `candidate_id` 使用 `manual:<stable-slug>`，并在 `citations` 中写明真实来源链接。

3. 生成 `runs/YYYY-MM-DD/brief.json`，结构必须符合 `candidates.json` 里的 `instructions_for_codex.schema`：
   - 语言：中文。
   - `page_summary` 必须是一段总结性的中文叙述，综合当天四个板块的走势、信息来源覆盖、明显缺口和对推荐系统研究的总体启发。
   - 四个板块都要有：`recsys_research`、`llm_hotspots`、`data_centric_ai`、`ai_social_tools`。
   - 每个板块先写趋势简报，趋势简报宁可多一点，不要漏重要方向。
   - 每个板块精选 5 条卡片；不足 5 条时按实际候选数量输出。
   - 每张卡片优先引用候选项的 `candidate_id`；如果是本 app 搜索补充项，则使用 `manual:<stable-slug>`。每张卡片都必须包含中文摘要、为什么值得看、对推荐系统的启发、来源引用。

4. 运行：

   ```bash
   python3 -m auto_search render runs/YYYY-MM-DD/brief.json
   ```

   注意：`render` 会根据 `.env` 中的 `PAGES_BASE_URL` 和 `PAGES_REPORTS_PATH` 生成飞书“阅读全文”链接。当前仓库根目录发布时应使用 `PAGES_REPORTS_PATH=docs/reports`。

5. 如果配置了 `FEISHU_BOT_WEBHOOK`，运行：

   ```bash
   python3 -m auto_search send-feishu runs/YYYY-MM-DD/feishu_card.json --brief runs/YYYY-MM-DD/brief.json
   ```

6. 尝试发布 GitHub Pages。如果没有 git remote，命令会安全跳过：

   ```bash
   python3 -m auto_search publish-pages --message "Update daily brief YYYY-MM-DD"
   ```

7. 如果任何关键步骤失败，尽量运行：

   ```bash
   python3 -m auto_search send-failure "AI研究情报日报失败：<简短原因>"
   ```

质量要求：

- 优先级同时考虑论文质量、讨论热度、与推荐系统的相关性、工具/产品实用价值。
- LLM、Data-centric AI、工具/产品板块都要显式说明对推荐系统研究可能有什么启发。
- 飞书卡片要精，详情页可以更完整。
- 如果某个来源不可用，不要整份失败；在简报里基于可用候选继续完成。
