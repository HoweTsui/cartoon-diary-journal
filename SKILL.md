---
name: cartoon-diary-journal
description: 把日记整理为原创黑白角色卡、表情动作预览与3:4日记海报，并兼容本地人物图谱和离线日记本。
---

# 原创黑白日记

把用户日记、照片和角色信息整理为原创角色卡、3:4日记海报、人物关系图谱与离线日记本。先保留完整原文，再明确选出1–5个场景；每天只交付一张海报，5场景仍按上到下顺序同页呈现。未选细节留在 `sourceText`，不自动改写、截断或编进海报。

## 固定流程

所有人物与动物的头部、身体必须按参考图侧向展示，绝对禁止正面，不保留背影例外；人物保留双眼可见的参考侧向画法。此硬性要求覆盖角色卡、表情、动作、新海报与旧图增补，交付逐角色目视核验。

开始时复用用户已保存的笔记工具/日记目录和日记本位置；未指定时只补问保存目标，先推进不依赖目标的整理。最终交付同时包含“目标笔记软件中的当天正文”和“对应 3D 日记本中的同日海报”。执行记录及交付核验见 `references/task-delivery.md`；不能把本地预览或仅生成文件称为已同步。

默认风格入口：每次阅读 `references/style-contract.md` 和 `references/style-lock.md`。已确认母版对所有新任务自动生效，不要求用户开启 styleLock；旧参考包不再默认使用。母版已批准与实验模板未批准分别管理，不自动批准草稿模板。

组件复用与动作库见 `references/component-reuse.md`：角色专属已确认动作优先直接复用，只等比缩放和平移。六个示例动作可供参考画法，但不能冒充用户身份；真实角色缺少匹配动作时，实际附上母版和角色卡生成单场景，不退回旧风格整页重画。

1. 阅读 `references/prompt-template.md`、`references/style-system.md`、`references/identity-fidelity.md`、`references/visual-gate.md`。生成人物时，生成器必须实际附上已批准母版及 identity-fidelity.md 中列出的全部角色组件参考；任何缺图、错配或可见身份/风格/表情偏差都不能验收为完成。
2. 用户提供照片时，先运行 `scripts/archive_diary_photos.py`：保留原件、另存长边2048px/质量85的JPEG，并让 brief 的 `origin: "user-photo"` 指向压缩件和归档清单。不要把用户照片放入 Skill 的固定参考包。
3. 新角色或旧角色卡画风不匹配时，用 `onboarding + --preview` 按母版校准人物卡。每个角色分别对应用户上传图像/已确认身份卡，逐项记录可见脸型、发型、年龄呈现、体型、服装及配饰锚点；按组件参考校准，不照搬示例角色整体。鼻形、鼻根断口、眼睛结构和比例按当前母版与 geometry 修正，不沿用旧卡的错误几何。新人物草稿档案录入图谱；未知关系不猜。用户确认该版本后记录 approvedVersion、approvedBy 和 `identity.styleVersion=style-lock-v2`，正式海报复用。待确认角色可用于明确标注的整页预览，不能替用户批准。
4. 写 brief，保留原文，明确每场一个动作重点和出镜角色。`role: "scene"` 图片必须有唯一 `id`，由对应事件的 `referenceIds` 显式引用，未映射时报错；身份卡可用 `characterIds` 限定角色，省略时兼容共享人物卡。映射格式见 `references/prompt-template.md`。运行 `scripts/build_diary_prompt.py` 和 `scripts/preflight_check.py`；每场用 `--scene N --request-output request-N.json` 导出工具实参，原样附上清单中筛选后的母版和本场参考图并保存实际调用记录。`--output` 提示词与 request 的 `prompt` 完全一致。角色比例唯一以 `references/geometry.json` 为准。
5. 每次生成一张**无文字、无纸张横线、透明背景**的独立场景。沿用母版侧向五官，场景自然留白，只画必要道具；禁止矩形背景、齐边截断和连续小分镜。逐张查看五官与完整边缘，再用 `scripts/build_diary_template.py --scenes ... --config ... --output-dir ...` 完整等比合成纸张与悠哉文字。按实际墨迹中心定位备注；顶部和右侧由本地安全区保护，横线贯穿备注区，无竖分隔线或白色遮挡。不得生成后硬裁人物、去白、以白板掩盖背景。
6. 更新实际人物图谱：用 `scripts/build_character_graph.py` 输出时会随HTML复制悠哉字体。将每篇正式日记按日期导入同一本日记本；`scripts/build_diary_reader.py` 会在缺失日期生成只含日期的留白页。旧版兼容构建器见 `references/diary-book-system.md`。
7. 阅读 `references/diary-document.md`，将完成文字合成的 PNG 压缩后直接嵌入对应日期日记正文，不能只交付链接。正文按“日记内容 → 完整海报 → 全部原照片三列宫格”排列，照片按输入顺序、用压缩件、不裁切。原件与高清海报保留，压缩后重新解码并对照检查异常变黑、空白、方向或失真。按目标工具的原生嵌图语法入库并实际预览；本地可用 `scripts/build_diary_document.py`。日记本汇编不能替代正文入库。

沿用以上七步，每步保存实际产物或调用证据到任务 `run.json`，交付前运行 `scripts/verify_diary_delivery.py run.json`。缺少笔记入库、日记本对应日期或实际预览证据就报告未完成项；脚本不伪造用户批准，也不声称能监控 Agent 的全部行为。

日记正文可轻润色语序、错别字和标点；正文及海报标题、备注、场景须逐条对照 `sourceText`，保留事实、因果、否定、情绪强度和用户立场，不新增情节或强行升华。字数限制不能成为改变原意的理由。

## 按任务查阅

- 修改旧海报、补充/替换元素：必须先读 `references/poster-revision.md`。当前画风同样约束旧图修改；旧图只作内容/构图参考，人物与动物都不能沿袭旧画法。
- 新角色/外观校准：`references/character-library.md`、`references/character-features.md`、`references/identity-fidelity.md`；扩展索引在 `assets/style-reference/character-extension-v1/library.json`。每次含人类角色的生图都必须实际附上头脸母版、外观变化、年龄/体型和开放式组合参考、24种正式表情参考，并按角色 ID 限定；必须另附对应角色的用户来源图或已确认身份卡。所有参考按声明的组件用途逐张使用，不复制参考图中的完整角色。
- 新动作/素材复用：`references/component-reuse.md`；当前动作索引 `assets/style-reference/style-lock-v1/action-library-v3.json`，逐项区分批准与示例草稿；旧动作仅存档。
- 选景/表情/排版：`references/prompt-template.md`、`references/visual-atoms.md`、`references/page-layouts.md`。
- 入库/同步/验收：`references/diary-document.md`、`references/task-delivery.md`、`references/diary-reader-v3.md`、`references/qa-checklist.md`；旧书兼容才查 `references/diary-book-system.md`。

正式生图要求 `identity.status=confirmed`、`version=approvedVersion`、`approvedBy=user` 和 `identity-approved` 图片。脚本不替用户作审批；替换正式资产或推送仓库仍要取得本次任务明确授权。

## 字体、颜色与图像质量

右侧备注默认 44px、标题48px、日期32px（1200px 宽画布，其他尺寸等比），字号统一由 `assets/templates/diary-poster-text-layout.json` 维护。长备注换行，禁止靠缩小字体塞入；超出安全区则调整表达或场景位置。场景以完整可见主体适配分配区域，只可略去外围完全透明的空白，不裁掉任何着色像素、身体白色填充或抗锯齿边缘，避免把大片透明画布当成主体导致图形过小。

人物头发使用简洁线条与留白，可依真实特征只选一处小面积黑色实填，不整片平涂黑色；保留发型辨识特征，详见 `references/character-features.md`。新版12人参考已确认并作为默认母版；只更新 Skill 示例，不擅自重画用户历史日记。

所有海报文字、关系图谱和两种日记本都使用 Skill 随附的 **悠哉 / Yozai**，运行环境不依赖设备安装字体。只使用白底、黑色墨线和浅青横线；浅青只用于横线。黑色实墨目标不超过画面20%，硬上限30%；3D翻页可有干净、轻微的中性灰投影，不能形成脏纹理。保留充足分辨率和正常平滑抗锯齿：最终海报、图谱与日记本屏幕显示都不能出现明显锯齿；禁止最近邻放大、硬边量化和刻意像素化。

运行：
```bash
python3 scripts/build_diary_prompt.py task-output/brief.json --preview --scene 1 --request-output task-output/request-01.json --output task-output/prompt-01.txt
python3 scripts/preflight_check.py --brief task-output/brief.json --preview
python3 scripts/check_poster_ink.py task-output/poster.png
python3 -m unittest discover -s tests
```

日记逐场替换 `--scene N` 和输出文件名；角色卡不带 `--scene`。不带请求导出的多事件提示词仅供规划，不能直接生图。正式模式省略 `--preview`。出图后按 `references/visual-gate.md` 与 `references/qa-checklist.md` 逐项检查身份、动作、文字安全区、颜色比例、字体、完整边界和正常缩放下的平滑度。预览未获用户认可前不得替换正式资产。隐私与原创边界见 `references/privacy-originality.md`。
