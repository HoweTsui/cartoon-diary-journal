# 维护者说明

本文件供仓库维护者使用；普通用户只需阅读 `README.md` 和 `SKILL.md`。

## 发布前检查

```bash
python3 scripts/preflight_check.py
python3 scripts/preflight_check.py \
  --graph /path/to/task-output/character-graph.html \
  --brief /path/to/diary-brief.json
SKILL_CREATOR_DIR="${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator"
UV_CACHE_DIR="${TMPDIR:-/tmp}/cartoon-diary-uv-cache" uv run --no-project --with pyyaml \
  python "$SKILL_CREATOR_DIR/scripts/quick_validate.py" \
  cartoon-diary-journal
```

第一条检查公开包结构，第二条检查一次真实任务的角色匹配闭环，最后一条检查 Skill 入口和脚手架完整性。

## GitHub 发布

不要把私人图谱、真人照片、任务 HTML 或本地生成物提交到公开仓库。发布前检查：

```bash
git status --ignored
git diff --check
git push origin main --follow-tags
```

## 版本管理

采用语义化版本 `MAJOR.MINOR.PATCH`：

- `PATCH`：修正提示词、校验逻辑或 HTML 小 bug，不改变调用方式。
- `MINOR`：增加兼容的新布局、关系编辑或宠物规则。
- `MAJOR`：改变目录、输入 JSON 或调用命令，需写迁移说明。

版本号写入 `VERSION`，变更写入 `CHANGELOG.md`。示例：

```bash
printf '0.1.3\n' > VERSION
git add VERSION CHANGELOG.md
git commit -m "fix: tighten character matching"
git tag -a v0.1.3 -m "小屁孩日记风格 Skill v0.1.3"
git push origin main --follow-tags
```
