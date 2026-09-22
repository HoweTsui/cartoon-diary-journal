---
name: cartoon-diary-journal
description: 把日记整理为原创黑白角色卡、表情动作预览与3:4日记海报，并兼容本地人物图谱和离线日记本。
---

# 原创黑白日记

把用户日记、照片和角色信息整理为原创角色卡、3:4日记海报、人物关系图谱与离线日记本。先保留完整原文，再明确选出1–5个场景；每天只交付一张海报，5场景仍按上到下顺序同页呈现。未选细节留在 `sourceText`，不自动改写、截断或编进海报。

## 固定流程

默认风格入口：每次阅读 `references/style-contract.md` 和 `references/style-lock.md`。已确认母版对所有新任务自动生效，不要求用户开启 styleLock；旧参考包不再默认使用。母版已批准与实验模板未批准分别管理，不自动批准草稿模板。

组件复用与动作库见 `references/component-reuse.md`：角色专属已确认动作优先直接复用，只等比缩放和平移。六个示例动作可供参考画法，但不能冒充用户身份；真实角色缺少匹配动作时，实际附上母版和角色卡生成单场景，不退回旧风格整页重画。

1. 阅读 `references/prompt-template.md`、`references/style-system.md`、`references/visual-gate.md`。生成器默认附上 `assets/style-reference/style-lock-v1/master-approved-v1.png`；该图只定义画法，用户身份来自本次角色卡。
2. 用户提供照片时，先运行 `scripts/archive_diary_photos.py`：保留原件、另存长边2048px/质量85的JPEG，并让 brief 的 `origin: "user-photo"` 指向压缩件和归档清单。不要把用户照片放入 Skill 的固定参考包。
3. 新角色或旧角色卡画风不匹配时，用 `onboarding + --preview` 按母版校准人物卡，保留发型、服装、配饰等身份锚点；鼻形、鼻根断口、眼睛结构和比例按当前母版与 geometry 修正，不沿用旧卡的错误几何。新人物草稿档案录入图谱；未知关系不猜。用户确认该版本后记录 approvedVersion、approvedBy 和 `identity.styleVersion=style-lock-v1`，正式海报复用。待确认角色可用于明确标注的整页预览，不能替用户批准。
4. 写 brief，保留原文，明确每场一个动作重点和出镜角色。`role: "scene"` 图片必须有唯一 `id`，由对应事件的 `referenceIds` 显式引用，未映射时报错；身份卡可用 `characterIds` 限定角色，省略时兼容共享人物卡。映射格式见 `references/prompt-template.md`。运行 `scripts/build_diary_prompt.py` 和 `scripts/preflight_check.py`；每场用 `--scene N --request-output request-N.json` 导出工具实参，原样附上清单中筛选后的母版和本场参考图并保存实际调用记录。`--output` 提示词与 request 的 `prompt` 完全一致。角色比例唯一以 `references/geometry.json` 为准。
5. 每次生成一张**无文字、无纸张横线、透明背景**的独立场景。沿用母版侧向五官，场景自然留白，只画必要道具；禁止矩形背景、齐边截断和连续小分镜。逐张查看五官与完整边缘，再用 `scripts/build_diary_template.py --scenes ... --config ... --output-dir ...` 完整等比合成纸张与悠哉文字。按实际墨迹中心定位备注；顶部和右侧由本地安全区保护，横线贯穿备注区，无竖分隔线或白色遮挡。不得生成后硬裁人物、去白、以白板掩盖背景。
6. 更新实际人物图谱：用 `scripts/build_character_graph.py` 输出时会随HTML复制悠哉字体。将每篇正式日记按日期导入同一本日记本；`scripts/build_diary_reader.py` 会在缺失日期生成只含日期的留白页。旧版兼容构建器见 `references/diary-book-system.md`。
7. 阅读 `references/diary-document.md`，将完成文字合成的 PNG 压缩后直接嵌入对应日期日记正文，不能只交付链接。正文按“日记内容 → 完整海报 → 全部原照片三列宫格”排列，照片按输入顺序、用压缩件、不裁切。原件与高清海报保留，压缩后重新解码并对照检查异常变黑、空白、方向或失真。按目标工具的原生嵌图语法入库并实际预览；本地可用 `scripts/build_diary_document.py`。日记本汇编不能替代正文入库。

日记正文可轻润色语序、错别字和标点；正文及海报标题、备注、场景须逐条对照 `sourceText`，保留事实、因果、否定、情绪强度和用户立场，不新增情节或强行升华。字数限制不能成为改变原意的理由。

正式生图要求 `identity.status=confirmed`、`version=approvedVersion`、`approvedBy=user` 和 `identity-approved` 图片。脚本不替用户作审批；替换正式资产或推送仓库仍要取得本次任务明确授权。

## 字体、颜色与图像质量

所有海报文字、关系图谱和两种日记本都使用 Skill 随附的 **悠哉 / Yozai**，运行环境不依赖设备安装字体。只使用白底、黑色墨线和浅青横线；浅青只用于横线。黑色实墨目标不超过画面20%，硬上限30%；3D翻页可有干净、轻微的中性灰投影，不能形成脏纹理。保留充足分辨率和正常平滑抗锯齿：最终海报、图谱与日记本屏幕显示都不能出现明显锯齿；禁止最近邻放大、硬边量化和刻意像素化。

运行：
```bash
python3 scripts/build_diary_prompt.py task-output/brief.json --preview --scene 1 --request-output task-output/request-01.json --output task-output/prompt-01.txt
python3 scripts/preflight_check.py --brief task-output/brief.json --preview
python3 scripts/check_poster_ink.py task-output/poster.png
python3 -m unittest discover -s tests
```

日记逐场替换 `--scene N` 和输出文件名；角色卡不带 `--scene`。不带请求导出的多事件提示词仅供规划，不能直接生图。正式模式省略 `--preview`。出图后按 `references/visual-gate.md` 与 `references/qa-checklist.md` 逐项检查身份、动作、文字安全区、颜色比例、字体、完整边界和正常缩放下的平滑度。预览未获用户认可前不得替换正式资产。隐私与原创边界见 `references/privacy-originality.md`。
