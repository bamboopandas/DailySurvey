# DailySurvey

每日 AI / 推荐系统情报项目。它由 Codex 自动化每天北京时间 08:00 生成日报，并在每月 1 日生成上月月报。系统使用本 app 内的 Codex `gpt-5.5` 做中文判断和写作；项目代码本身不调用 OpenAI 或其他外部 LLM API。

说明：项目会访问 arXiv、OpenReview、Semantic Scholar、GitHub、RSS/网页等公开来源来抓取原始信息；这些是信息源接口/网页，不是外部 LLM。真正的“理解、筛选、总结、写简报”由 Codex 自动化里的 `gpt-5.5` 完成。如果某个板块候选不足，自动化可以继续使用本 app 内置搜索/浏览能力补充公开来源。

## 工作流

1. `collect` 抓取公开来源，生成 `runs/YYYY-MM-DD/candidates.json`。
2. Codex 自动化读取候选集，用 `gpt-5.5` 生成新闻写法的 `runs/YYYY-MM-DD/brief.json`。
3. `render` 生成 `docs/reports/YYYY-MM-DD/index.html` 和 `runs/YYYY-MM-DD/feishu_card.json`。
4. `send-feishu` 通过飞书自定义机器人发送卡片，并在成功后更新 `state/seen.json`。
5. `publish-pages` 在配置了 git remote 后提交并推送 `docs/`，用于更新 GitHub Pages。

月报流程：

1. `prepare-monthly` 汇总上月已有日报和候选集，生成 `runs/monthly/YYYY-MM/monthly_input.json`。
2. Codex 自动化用 `gpt-5.5` 写 `runs/monthly/YYYY-MM/monthly_brief.json`。
3. `render` 生成 `docs/monthly/YYYY-MM/index.html` 和月报飞书卡片。

## 环境变量

复制 `.env.example` 为 `.env`，至少配置：

```bash
FEISHU_BOT_WEBHOOK=
FEISHU_BOT_SIGN_SECRET=
PAGES_BASE_URL=
PAGES_REPORTS_PATH=docs/reports
PAGES_MONTHLY_PATH=docs/monthly
SEMANTIC_SCHOLAR_API_KEY=
```

`FEISHU_BOT_WEBHOOK` 是必需项。`FEISHU_BOT_SIGN_SECRET` 和 `SEMANTIC_SCHOLAR_API_KEY` 是可选项。`PAGES_BASE_URL` 建议配置为 GitHub Pages 站点根地址，例如 `https://USER.github.io/REPO`。

如果 GitHub Pages source 选择仓库根目录，保留 `PAGES_REPORTS_PATH=docs/reports` 和 `PAGES_MONTHLY_PATH=docs/monthly`；如果 source 选择 `/docs` 目录，则分别改成 `reports` 和 `monthly`。

## 本地命令

```bash
python3 -m auto_search collect --lookback-hours 48
python3 -m auto_search scaffold-brief runs/$(date +%F)/candidates.json
python3 -m auto_search render runs/$(date +%F)/brief.json
python3 -m auto_search send-feishu runs/$(date +%F)/feishu_card.json --brief runs/$(date +%F)/brief.json
python3 -m auto_search publish-pages
```

生成月报输入：

```bash
python3 -m auto_search prepare-monthly --month 2026-04
```

无 LLM 的端到端 dry-run：

```bash
python3 -m auto_search run --lookback-hours 48
```

发送测试需要真实飞书 Webhook：

```bash
python3 -m auto_search send-feishu runs/$(date +%F)/feishu_card.json --brief runs/$(date +%F)/brief.json --allow-fallback
```

正式日报不要发送 `scaffold-brief` 生成的兜底简报；`send-feishu` 默认会拒绝发送 `_fallback_brief=true` 的文件，避免误把测试内容推到飞书。

## Codex 自动化

自动化应使用 `gpt-5.5` 和 high reasoning。日报提示词参考 `scripts/automation_prompt.md`，月报提示词参考 `scripts/monthly_automation_prompt.md`。自动化负责生成高质量 `brief.json` / `monthly_brief.json`，不要改成在代码里调用外部 LLM API。

## GitHub Pages

报告输出到 `docs/`，页面包含 `noindex,nofollow`。当前默认兼容 GitHub Pages source 选择仓库根目录，此时日报地址形如 `https://USER.github.io/REPO/docs/reports/YYYY-MM-DD/`。

如果你把 Pages Source 改成 `/docs` 目录，则 `.env` 中设置 `PAGES_REPORTS_PATH=reports`，日报地址会变成 `https://USER.github.io/REPO/reports/YYYY-MM-DD/`。

月报默认输出到 `docs/monthly/YYYY-MM/`，当前根目录发布时地址形如 `https://USER.github.io/REPO/docs/monthly/YYYY-MM/`。

如果当前目录还没有 git 仓库：

```bash
git init
git branch -M main
git remote add origin <你的 GitHub 仓库地址>
```

`state/`、`runs/`、`.env` 和日志默认不提交。
