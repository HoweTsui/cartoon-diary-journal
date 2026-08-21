# 小屁孩日记风格 Skill

一个面向 Codex 的原创黑白日记插画 Skill：用极简中粗墨线、单行本浅蓝横线纸、夸张动作和短对话，把一天整理成 9:16 竖版日记页；同时用可拖拽 HTML 关系图维护角色身份与关系。

> 展示名称按用户指定使用“小屁孩日记风格 Skill”。生成规则只采用黑白日记纸、稚拙线描、夸张肢体、克制幽默等非专属特征，不复制任何已出版作品的具体角色、字体、页面或笑点。

![日记页风格参考](assets/style-reference/diary-style-anchor.png)

## 核心流程

```text
日记请求
  → 读取本次任务 character-graph.html
  → 逐一匹配角色 ID / 姓名 / 身份锚点
  → 命中：复用对应头像格位与外观锚点
  → 未命中：暂停生图，要求上传角色图片
  → 统一转绘后补入图集、关系 JSON 和 HTML
  → 重新匹配通过
  → 生成 9:16 日记页并做 QA
```

“自动补充”指收到缺失角色图片后自动完成转绘、数据合并、HTML 重建和再次匹配；没有图片时不会猜测人物，也不会用旧占位角色顶替。

## 生成约束

- 顶部第一信息固定为 `YYYY.MM.DD 周X`，严格 9:16。
- 14–18 条等距极浅蓝横线，3–6 个场景从上到下连续排版，不画四格边框。
- 统一中粗纯黑线、双完整点眼、单鼻、低位嘴、细长双线小腿和偏大扁鞋；禁止写实、渐变、噪点和混合线重。
- 人物身份由图谱锚点锁定；宠物保留物种结构，动物眼睛无白色高光，狗鼻为前端黑色椭圆，猫鼻更小且位于双眼下方中央。
- 关系图谱是全局资料，不写日期；浏览态纯文本，编辑态支持拖拽连线、断开关系、关系名双击编辑、智能编排、撤销/重做。

## 使用

### 安装到 Codex

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R ./cartoon-diary-journal "${CODEX_HOME:-$HOME/.codex}/skills/"
```

在 Codex 中调用：

```text
Use $cartoon-diary-journal
先检查本次人物关系图，再把下面内容生成一页日记；缺失角色先要求补图入库。
```

### 构建实际人物图谱

不要直接修改仓库里的本地图谱或沿用旧人物。先复制结构模板，填入本次任务的真实角色、关系和图集格位，再整体替换 HTML：

```bash
python3 scripts/build_character_graph.py \
  /path/to/actual-character-data.json \
  --output /path/to/task-output/character-graph.html
```

把重新生成的 `character-lineup.png` 放到 HTML 同目录后再生成提示词。`graph-data.status` 必须为 `actual`；所有旧姓名、旧关系、旧备注和旧锚点必须被整体替换。私人照片只作为当次临时输入，不能提交到 GitHub。

### 生成稳定提示词

```bash
python3 scripts/build_diary_prompt.py \
  /path/to/diary-brief.json \
  --graph /path/to/task-output/character-graph.html \
  --output /path/to/task-output/diary-prompt.txt
```

脚本会校验图谱状态、头像格位、关系端点、角色命中、日期真实性和中文周几；缺失或歧义角色会以非零状态中止。

## 发布前预检

```bash
python3 scripts/preflight_check.py
python3 scripts/preflight_check.py \
  --graph /path/to/task-output/character-graph.html \
  --brief /path/to/diary-brief.json
UV_CACHE_DIR=/private/tmp/cartoon-diary-uv-cache uv run --no-project --with pyyaml \
  python /Users/ftd/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  cartoon-diary-journal
```

第一条检查公开包结构；第二条检查一次真实任务的匹配闭环；最后一条检查 Skill 入口、命名和脚手架完整性。

## GitHub 发布

建议为日记 Skill 建立独立仓库，避免把本地私人图谱一起公开：

```bash
cd cartoon-diary-journal
git init
git add .
git commit -m "feat: release diary illustration skill v0.1.0"
git branch -M main
git remote add origin https://github.com/<你的账号>/<仓库名>.git
git push -u origin main
```

仓库内的 `.gitignore` 会排除本地任务图谱、人物图集和私人角色数据；发布前用 `git status --ignored` 检查一次，确认没有照片、私有 HTML 或本地生成物。

## 版本管理

采用语义化版本 `MAJOR.MINOR.PATCH`：

- `PATCH`：修正提示词、校验逻辑或 HTML 小 bug，不改变调用方式。
- `MINOR`：增加兼容的新布局、关系编辑或宠物规则。
- `MAJOR`：改变目录、输入 JSON 或调用命令，需写迁移说明。

版本号写入 [`VERSION`](VERSION)，变更写入 [`CHANGELOG.md`](CHANGELOG.md)。发布新版本：

```bash
printf '0.1.1\n' > VERSION
git add VERSION CHANGELOG.md
git commit -m "fix: tighten character matching"
git tag -a v0.1.1 -m "小屁孩日记风格 Skill v0.1.1"
git push origin main --follow-tags
```

## 目录

```text
cartoon-diary-journal/
├── SKILL.md
├── README.md
├── LICENSE
├── VERSION
├── CHANGELOG.md
├── agents/openai.yaml
├── references/                 # 风格、图库、版式、隐私与 QA 规则
├── scripts/                    # 图谱构建、提示词生成、发布前预检
└── assets/
    ├── style-reference/        # 可公开的风格参考
    └── templates/               # 实际任务数据结构模板
```

## 许可与隐私

代码与文档沿用上层仓库的 MIT 许可。不要提交真人原图、宠物原图、真实关系、地点、日期截图或未脱敏的任务 HTML；公开仓库只保留原创生成参考资产和结构模板。
