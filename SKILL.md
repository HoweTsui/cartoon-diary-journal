---
name: cartoon-diary-journal
description: 把日记整理为原创黑白角色卡、表情动作预览与3:4日记海报，并兼容本地人物图谱和离线日记本。
---

# 原创黑白日记

用户提供日记、照片或角色信息后，Agent 先保留完整原文，再语义编写标题、短备注和明确选定的1–5场景。每天只交付一张3:4海报；5个场景也不拆页，改为简化背景、合并重复动作和缩短短备注来保持阅读顺序。不要把脚本当摘要器，不截断文字，不以关键词默认推断中性表情。未选入海报的细节仍完整留在 sourceText；向用户说明海报是选景摘要。

读取 references/prompt-template.md 的 schema 和 references/style-system.md 的视觉规则。唯一数值几何定义为 references/geometry.json；其他规范不得追加覆盖比例。物种各有固定尺寸，不按上次结果逐轮缩小身体。

风格纠偏时保留用户已认可部分：当前人类臂腿粗细不动；五官采用横向宽扁开放鼻及鼻根上方明显断口、等径正圆小眼、低位偏耳侧的嘴；嘴长与嘴形随具体表情变化。细脖子、等粗描边与圆头线端；正常及轻中度表情无眉，仅明确强烈夸张表情可临时加眉。细节以 style-system.md 为准。动物保持短细肢体、夸张大爪与完全无毛的光滑轮廓。旧身份图的错误几何不能覆盖新规范。

先识别 protagonistId 和本次角色。新角色可以只有用户授权的身份图片与文字锚点，无需已存在的合格图谱。使用 onboarding + --preview 生成新草稿角色卡，并将名称、关系、首次出现日记和草稿人物档案加入关系图；用户认可人物小卡后，才将其标记为可用于正式成品。老图的身份大特征保留，错误几何不沿袭。用户要求测试时，可基于 identity-draft 继续生成 expression 或 diary 预览，不代表审批通过。

正式生图要求 identity.status=confirmed、version 与 approvedVersion 相同、approvedBy=user，以及 identity-approved 图片。只有用户明确批准当前版本后由 Agent 记录；脚本不自动批准。优化建议获批不等于生成身份图获批。替换正式海报、原仓库或已安装 Skill 仍遵守本次用户授权范围。

运行：
```bash
python3 scripts/build_diary_prompt.py task-output/brief.json --preview --output task-output/prompt.txt
python3 scripts/preflight_check.py --brief task-output/brief.json --preview
python3 -m unittest discover -s tests
```
正式模式省略 --preview；可选 --graph 指向任务图谱，缺失 species 时须在 brief 明确提供角色。所有新输入图片路径相对 brief 目录，声明的图片必须存在。生成器输出仅为提示词；调用生图工具时还须实际附上每张引用图。

出图后按 references/visual-gate.md 和 references/qa-checklist.md 人工检查身份、动作、几何、文字与完整边界；结构预检不能证明图片视觉合格。预览交用户批准前不得替换正式资产。

人物图谱仍使用 scripts/build_character_graph.py，读取 references/character-library.md；点击节点时在右侧查看人物档案、标准卡、关系和首次出现日记。新版日记本使用 scripts/build_diary_reader.py 和 references/diary-reader-v3.md：每篇正式日记都导入同一本书，按日期连续排列，缺失日期生成只含日期的留白页；保留海报原图，以手写纸页、花瓣封面蒙版及真实3D翻页展示。窄屏以可读的大画幅显示，不得把书缩小到不可辨认。旧清单规范及兼容构建器 scripts/build_diary_book.py 见 references/diary-book-system.md；不改写历史内容。未迁移的历史图谱能读，不作为新图的审批证据。隐私规则见 references/privacy-originality.md。
