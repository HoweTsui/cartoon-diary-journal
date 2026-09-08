# 原创黑白日记 Skill

支持原创角色卡、表情动作测试、1–4选景的3:4日记海报；保留人物图谱与离线日记本接口。

先读[SKILL.md](SKILL.md)，输入契约见[Schema v2](references/prompt-template.md)。完整原文保留，Agent语义编写短文本，构建器不截断或推断。

```bash
python3 scripts/build_diary_prompt.py task-output/brief.json --preview --output task-output/prompt.txt
python3 scripts/preflight_check.py --brief task-output/brief.json --preview
python3 -m unittest discover -s tests
```

正式生图需要当前版本的用户身份审批；测试预览不自动批准。数值定义见[geometry.json](references/geometry.json)，图像仍需人工验收。

新版[手写3D日记本](references/diary-reader-v3.md)使用 Quick FlipBook：纸白浅青横线、手写字体、可编辑标题、可替换图片的花瓣蒙版封面，以及目录搜索、阅读进度、原图放大。随包提供本地运行时和导入脚本，不含本地日记数据。海报原图完整展示，不裁切或重画。

原有图谱与旧日记本构建器、运行时保持兼容。历史 Demo 图片仅作旧数据与版式示例，不作为当前角色几何或身份审批依据。参考[人物库](references/character-library.md)与[旧日记本数据契约](references/diary-book-system.md)。

安装：将此仓库完整放入 `$CODEX_HOME/skills/cartoon-diary-journal`（默认 `~/.codex/skills/cartoon-diary-journal`），重新加载会话后使用 `$cartoon-diary-journal`。日记海报与日记本属于同一个 Skill。

v0.3.0 使用 Schema v2；旧 brief 需按新模板迁移，明确 sourceText、protagonistId、species、场景表情和身份审批状态，不能直接沿用旧输入。先在已忽略的 task-output/ 中编写本次 brief，图片路径相对 brief 所在目录。
