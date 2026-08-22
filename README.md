# 小屁孩日记风格 Skill

一个面向 Codex 的原创黑白日记插画 Skill：把一天的经历整理成 9:16 竖版单行本日记页，并用可拖拽 HTML 关系图保持人物和宠物形象一致。

> 这里只提取黑白稚拙线描、夸张动作、短对话和单行本横线纸等非专属特征，不复制任何已出版作品的具体角色、字体、页面或笑点。

## 它能做什么

- 生成带 `YYYY.MM.DD 周X` 顶部标题的 9:16 日记海报。
- 用 3–6 个纵向场景讲清一天的小故事，支持对话气泡和简短旁白。
- 先检索本次任务的人物关系图谱，再复用角色头像和外观锚点。
- 角色缺失时暂停生成，提示上传图片；转绘入库并更新图谱后再继续。
- 提供全局人物关系图：浏览态只读，编辑态支持拖拽连线、断开关系、关系名编辑、智能编排和撤销/重做。

## 公开示例

下面的示例只使用公开占位角色，不包含任何私人姓名、照片或任务数据。

### 日记海报

![黑白日记海报示例](assets/style-reference/diary-style-anchor.png)

### 人物关系图谱

关系图谱不按日期组织，作为全局人物参考使用；点击节点可查看角色卡，编辑模式支持节点和关系调整。

![公开人物关系图谱 HTML 页面截图](assets/style-reference/character-graph-concept.png)

[打开公开关系图谱示例 HTML](assets/style-reference/character-graph-demo.html)

## 画面规则

- 黑白中粗墨线、低噪点、无渐变、无灰色阴影；只允许单行本浅蓝横线作为纸张辅助色。
- 页面为 9:16 竖版，顶部先放日期和周几，再放标题；场景从上到下排版，不画四格边框。
- 人物采用固定轻微三分之二侧脸，必须看见两只豆豆眼；脸部轮廓是连续平滑曲线，不能出现折点、直角或阶梯转折。
- 手臂和前臂保持极细双线管状，手掌略放大但仍小巧（3–4 个短指弧）；小腿为细长双线，鞋子略大且扁。
- 动物保留物种结构但保持极简：黑白线稿、无写实毛发、无眼睛高光；狗鼻为前端黑色椭圆，猫鼻更小且位于双眼下方中央。

## 安装到 Codex

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R ./cartoon-diary-journal "${CODEX_HOME:-$HOME/.codex}/skills/"
```

在 Codex 中调用：

```text
Use $cartoon-diary-journal
先检查本次人物关系图，再把下面内容生成一页日记；缺失角色先要求补图入库。
```

## 使用实际人物图谱

不要直接沿用仓库里的示例人物。先复制模板，填入本次任务的真实角色、关系和图集格位，再生成任务专用 HTML：

```bash
python3 scripts/build_character_graph.py \
  /path/to/actual-character-data.json \
  --output /path/to/task-output/character-graph.html
```

把任务图集放到 HTML 同目录。`graph-data.status` 必须为 `actual`，旧姓名、旧关系、旧备注和旧锚点必须整体替换。私人照片只作为当次临时输入，不能提交到公开仓库。

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
├── scripts/                    # 图谱构建等辅助脚本
└── assets/
    ├── style-reference/        # 可公开的风格参考
    └── templates/               # 实际任务数据结构模板
```

## 许可与隐私

代码与文档沿用上层仓库的 MIT 许可。不要提交真人原图、宠物原图、真实关系、地点、日期截图或未脱敏的任务 HTML；公开仓库只保留原创生成参考资产和结构模板。
