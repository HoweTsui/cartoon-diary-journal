---
name: cartoon-diary-journal
description: 把日记整理为原创黑白角色卡、表情动作预览与3:4日记海报，并兼容本地人物图谱和离线日记本。
---

# 原创黑白日记

把用户日记、照片和角色信息整理为原创角色卡、3:4日记海报、人物关系图谱与离线日记本。先保留完整原文，再明确选出1–5个场景；每天只交付一张海报，5场景仍按上到下顺序同页呈现。未选细节留在 `sourceText`，不自动改写、截断或编进海报。

## 固定流程

1. 先阅读 `references/prompt-template.md`、`references/style-system.md`、`references/visual-gate.md`。`assets/style-reference/reference-manifest.json` 是每次必须随生图实际附上的固定参考包：人物画风、人物/动物表情、无人物3:4日记模板；它只定义画风与版式，不提供任何用户身份。
2. 用户提供照片时，先运行 `scripts/archive_diary_photos.py`：保留原件、另存长边2048px/质量85的JPEG，并让 brief 的 `origin: "user-photo"` 指向压缩件和归档清单。不要把用户照片放入 Skill 的固定参考包。
3. 有新角色时，用 `onboarding + --preview` 生成一张人物形象卡：全身、脸部细节、从输入提取的可见身份锚点。把草稿人物档案（名称、首次出现、已知关系）录入图谱；未知关系不猜。向用户展示卡片，用户明确确认该版本后才将其标记 `approved`，后续正式海报复用该卡，不重复确认。测试可使用草稿卡，但不等于批准。
4. 写 brief 后运行 `scripts/build_diary_prompt.py` 和 `scripts/preflight_check.py`。生成器会自动注入并校验固定参考包；调用生图工具时必须把输出中列出的每张图实际附上。角色比例唯一以 `references/geometry.json` 为准，旧图错误不得沿袭。
5. 先生成**无文字**插画：顶部预留日期/标题，右侧不画人物道具，但浅青横线完整贯穿右侧。检查成图后逐场记录整页归一化高度 `sceneCenters`，一条备注对应一个场景中心；用 `scripts/build_diary_text_layer.py --anchors <坐标JSON>` 放置悠哉文字。文字层透明、无竖分隔线，不用白面板遮挡插画或横线。若右侧被插画侵占，先修复插画留白。不能让生成模型直接渲染日期、标题或备注。
6. 更新实际人物图谱：用 `scripts/build_character_graph.py` 输出时会随HTML复制悠哉字体。将每篇正式日记按日期导入同一本日记本；`scripts/build_diary_reader.py` 会在缺失日期生成只含日期的留白页。旧版兼容构建器见 `references/diary-book-system.md`。

正式生图要求 `identity.status=confirmed`、`version=approvedVersion`、`approvedBy=user` 和 `identity-approved` 图片。脚本不替用户作审批；替换正式资产或推送仓库仍要取得本次任务明确授权。

## 字体、颜色与图像质量

所有海报文字、关系图谱和两种日记本都使用 Skill 随附的 **悠哉 / Yozai**，运行环境不依赖设备安装字体。只使用白底、黑色墨线和浅青横线；浅青只用于横线。黑色实墨目标不超过画面20%，硬上限30%；3D翻页可有干净、轻微的中性灰投影，不能形成脏纹理。保留充足分辨率和正常平滑抗锯齿：最终海报、图谱与日记本屏幕显示都不能出现明显锯齿；禁止最近邻放大、硬边量化和刻意像素化。

运行：
```bash
python3 scripts/build_diary_prompt.py task-output/brief.json --preview --output task-output/prompt.txt
python3 scripts/preflight_check.py --brief task-output/brief.json --preview
python3 scripts/check_poster_ink.py task-output/poster.png
python3 -m unittest discover -s tests
```

正式模式省略 `--preview`。出图后按 `references/visual-gate.md` 与 `references/qa-checklist.md` 逐项检查身份、动作、文字安全区、颜色比例、字体、完整边界和正常缩放下的平滑度。预览未获用户认可前不得替换正式资产。隐私与原创边界见 `references/privacy-originality.md`。
