<p align="center">
  <img src="assets/readme/cover.png" alt="小屁孩日记风格 Skill 封面" width="100%">
</p>

<p align="center">
  <strong>把一天的小事，画成角色一致、从上到下讲故事的 3:4 黑白日记海报。</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-111111.svg" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/Codex-Skill-62c5d8.svg" alt="Codex Skill">
  <img src="https://img.shields.io/badge/Version-0.2.4-111111.svg" alt="Version 0.2.4">
</p>

本项目是一套原创黑白幽默日记插画 Skill。它会先检索人物关系图，再根据日记内容生成海报，让同一人物和宠物在连续页面中保持一致；已验收的连续海报还能汇编成完全离线的可翻页日记本。

> 只提取黑白稚拙线描、日记纸、夸张动作和短对话等非专属特征，不复制已出版作品的具体角色、字体、页面或笑点。

## 先看效果

### 日记海报

<p align="center">
  <img src="assets/style-reference/diary-style-anchor-3x4.png" alt="3:4 黑白日记海报示例" width="430">
</p>

### 可编辑人物关系图

![人物关系图谱 HTML 页面截图](assets/style-reference/character-graph-concept.png)

浏览态用于查看人物卡和关系；节点优先加载各自独立的 1:1 上半身头像并居中，整张图集只作总览和旧数据兜底。点击“编辑”后可拖拽节点、建立或断开连线、修改关系名称、自动编排、撤销和重做。

[打开可交互示例 HTML](assets/style-reference/character-graph-demo.html)

### 离线可翻页日记本

<p align="center">
  <img src="assets/diary-book/demo/cover-assets/cover-main-3x4.png" alt="离线可翻页日记本虚构示例封面主视觉" width="240">
</p>

日记本保持每张海报的原始比例完整显示：新海报采用 3:4，历史 9:16 海报使用 `contain` 置入 3:4 书页，不裁切、不拉伸。翻页舞台使用白纸、浅青横线、黑墨线和轻量装订感；封面采用彩色书皮、撕纸蒙版和独立可编辑标题，不复制已出版作品的角色、Logo 或字体。日记页不重复叠加日期和标题，只在页脚显示摘要、标签和页码；同时提供桌面双页、手机单页、目录、日期/标题/标签/角色搜索、`#entry` 深链和按日记 ID 恢复的本地阅读进度。书内人物卡与只读关系概览会跳转到独立人物图谱，并通过 `?character=<角色ID>` 自动选中节点；不把图谱 Canvas 嵌入翻页页。

[打开虚构离线 Demo](assets/diary-book/demo/index.html)（下载或克隆仓库后直接用浏览器打开）

## 能做什么

| 日记编排 | 角色一致性 | 人物关系图 |
| --- | --- | --- |
| 居中日期/周几、居中标题和 3–6 个纵向场景 | 复用头像、五官、比例、服装与宠物锚点 | HTML 节点拖拽、独立 1:1 头像、关系编辑与智能编排 |
| 固定字号的右侧场景备注和少量对话气泡 | 新角色先转绘入库，再生成日记 | 支持增删角色、修改详情和导出数据 |

主要产出：

- 3:4 黑白日记海报 PNG（历史 9:16 海报仅作兼容）。
- 任务专用人物关系图 HTML（每个节点优先读取独立 1:1 上半身头像并居中显示）。
- 角色图集和可复用身份锚点。
- 本地私有的离线可翻页日记本 HTML（每日海报不裁切、不重排）。

## 安装

### 推荐：让 AI Agent 安装

把下面这句话发给有本地终端权限的 AI Agent：

```text
请安装这个 Codex Skill，并在安装后检查 SKILL.md 是否存在：
https://github.com/HoweTsui/cartoon-diary-journal
```

Agent 应安装到：

```text
${CODEX_HOME:-$HOME/.codex}/skills/cartoon-diary-journal
```

### Skills CLI

```bash
npx skills add HoweTsui/cartoon-diary-journal --skill cartoon-diary-journal --agent codex --global
```

只有使用 `npx skills` 安装器时才需要 Node.js；Skill 本身不依赖 Node.js。

### 手动安装

```bash
skill_dir="${CODEX_HOME:-$HOME/.codex}/skills/cartoon-diary-journal"
if [ -d "$skill_dir/.git" ]; then
  git -C "$skill_dir" pull --ff-only
else
  mkdir -p "$(dirname "$skill_dir")"
  git clone https://github.com/HoweTsui/cartoon-diary-journal.git "$skill_dir"
fi
```

## 第一次使用

在 Codex 中直接说：

```text
Use $cartoon-diary-journal
把下面经历整理成一页 3:4 黑白日记海报：
日期：2026-08-24
标题：更新先走了一步
内容：电脑更新时，我先把零散想法写进日记，猫咪踩乱了一张纸。
```

也可以附上照片、聊天记录或事件清单。Skill 会先确认日期、出场角色和人物图谱，再开始生成。

## 工作方式

```text
日记内容
   ↓
检索人物关系图和角色图集
   ├─ 已存在：复用身份锚点
   └─ 不存在：请求参考图 → 统一转绘 → 补入图谱
   ↓
每名角色生成独立 1:1 头像 → 拼成完整总览图集
   ↓
生成 3:4 纵向日记海报
   ↓
检查日期、角色、五官、肢体、文字和色彩
   ↓
可选：汇编为离线可翻页日记本
```

## 核心画面规则

- 纯黑白中粗墨线、纯白纸面；只允许浅蓝单行本横线。
- 顶部固定且居中 `YYYY.MM.DD 周X`，下一行放居中标题；日期和标题使用跨页面固定字号层级，正文按 3–6 个场景从上到下排列。
- 人物和动物统一采用 25°–35° 偏正半侧面，必须看见两只同尺寸正圆豆豆眼；眼点直径锁定确认版图集的 canonical diameter，不因场景或表情放大；禁止正面和单眼正侧面。
- 人脸轮廓平滑；前外侧眼旁短弧后到鼻根保留约 1.5 个眼点高度的空白断口，不画眉毛或鼻梁。
- 人物鼻使用上方开口、不填黑的线描半椭圆；动物使用物种正确的实心黑鼻，两者不能互换。
- 身板窄；人物上臂、前臂、大腿、小腿与动物不含爪掌的前后肢杆部首轮目标约为头宽 1/32、绝不超过约 1/24，彼此粗细误差不超过 10%；短裤可稍宽，但小腿必须在裤脚处立刻收窄。
- 可见配饰（包括眼镜框、镜桥和镜腿）与人物主体统一使用 5–6px 纯黑线，不得单独变粗、变细或改成发丝线。
- 所有人物和动物都必须朝左或右 25°–35° 半侧面，鼻尖/口鼻横向伸出；禁止正对镜头、居中鼻子、对称双耳/双肩或正面头脸接半侧面身体。动物爪掌略大但爪掌外肢体仍保持同样细，不画写实毛发、阴影或眼睛高光。
- 每场使用固定字号的 4–10 字短总结，并放在该行插画右侧的备注栏；相邻场景保留明显空白。表情根据该格日记事件变化，气泡只放 1–6 字短反应，整页最多 3 个。

完整规范见 [SKILL.md](SKILL.md) 与 [references/](references/)。

## 人物关系图

关系图是全局角色参考，不按日期组织。生成实际任务图谱时，先填写任务数据，再构建 HTML：

每名角色先生成独立的 1:1 方形上半身 PNG 或 SVG，并在节点中填写唯一的 `avatarSrc`（相对 HTML 路径）；再按相同顺序拼成 `character-lineup.png` 或 `.svg` 总览图。HTML 节点和人物卡会以中心对齐优先读取独立头像，旧数据才回退图集裁切。`?character=<角色ID>` 可让图谱自动选中并居中指定人物。

```bash
python3 scripts/build_character_graph.py \
  /path/to/actual-character-data.json \
  --output /path/to/task-output/character-graph.html
```

## 汇编离线可翻页日记本

真实清单、角色头像、图谱、海报和输出都保留在 Git 忽略的 `task-output/`。日记本不裁切、不重排已有海报；新海报为 3:4，历史 9:16 海报完整放入 3:4 书页。构建时会复制固定的本地翻页运行时，因此不需要网络、CDN 或服务端。

```bash
python3 scripts/build_diary_book.py \
  task-output/diary-book/diary-book-data.local.json \
  --graph task-output/diary-book/character-graph.html \
  --output task-output/diary-book/index.html
```

数据字段、时期规则、隐私边界和验收标准见 [diary-book-system.md](references/diary-book-system.md)。公开虚构 Demo 可用 `--public-demo` 重建，真实内容不能使用该参数。

## 项目结构

```text
cartoon-diary-journal/
├── SKILL.md                 # Skill 主规则
├── agents/openai.yaml       # Agent 显示信息
├── references/              # 风格、版式、图库与 QA 规则
├── scripts/                 # 图谱、提示词、日记本构建和辅助脚本
└── assets/
    ├── diary-book/          # 本地翻页运行时与虚构 Demo
    ├── readme/              # README 封面素材
    ├── style-reference/     # 公开示例与风格参考
    └── templates/           # 任务数据模板
```

## 适用范围

适合个人日记、生活记录和连续角色故事；不适合写实人像、摄影风、三维渲染、复杂彩色插画，或复刻已出版作品的具体角色与页面。

## License

[MIT](LICENSE)
