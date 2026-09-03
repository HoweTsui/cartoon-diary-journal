# 离线可翻页日记本系统

## 目标与边界

日记本把已经验收的每日海报整理为离线可翻页 HTML。新版（v0.2.2）所有新封面、书页和日记海报使用严格 3:4；历史 9:16 海报保留原始尺寸，以 `object-fit: contain` 完整置入 3:4 书页，不裁切、不拉伸、不重排、不覆盖原内容。

- 使用随 Skill 固定的 `page-flip@2.0.7` 浏览器包；无 CDN、无服务端、无分析脚本。
- 桌面端双页，移动端单页；封面/封底为硬页，其余为软页；每一张单页都保持 3:4。
- 书页视觉与人物关系图谱共用纸白、浅青横线、黑色墨线、细矩形边框和克制阴影。
- 书内关系概览只读；人物卡和关系节点只跳转到独立 `character-graph.html?character=<角色ID>`，绝不嵌入可编辑图谱。
- 阅读进度以 `bookId + entryId` 保存到浏览器 `localStorage`，不会上传；新增日记后仍回到同一篇。

## 视觉系统（v0.2.2）

封面不是扁平网页卡片，而是可编辑的书籍结构：中等明度的砖红、陶土橙、墨绿或复古蓝书皮；3%–4% 内缩装订框；上部三层标题；中央纸白不规则 SVG 蒙版；用户图片、纸胶带和原创黑白线稿占位图。封面颜色由 CSS 变量控制，禁止黑色/石墨色大面积底色、渐变、发光、玻璃效果、噪点和写实皮纹。标题必须由 HTML/SVG 文本渲染，不能烘焙进 ImageGen 位图。

- `coverImageSrc` 存在时，将图片放入中央不规则蒙版，默认 `object-position: 50% 50%`；缺省时显示原创线稿占位图。
- `coverTitle`、`coverSubtitle`、`coverEyebrow` 独立可编辑；封面图片只提供纸张、纹理、线稿或装饰，不生成文字、Logo 或已出版角色。
- 翻页舞台使用浅色桌面与白纸书页，不使用灰色大卡片、厚重圆角容器、胶囊按钮或强阴影。
- 日记页、人物介绍页、时期扉页和关系概览页全部是 3:4；日期和标题不在书页重复覆盖海报，页脚只显示摘要、标签、角色和页码。
- 人物介绍头像必须是独立 1:1 方形上半身，完整居中；人物五官、极细肢体、半侧面、可见配饰（包括眼镜框、镜桥和镜腿）的统一线宽以及右侧备注栏规则沿用 Skill 原有门禁。

## 私有数据与公开 Demo

真实日记清单、海报、真实角色头像、关系图和输出只能放在 `task-output/`，且必须保持 Git 忽略。公开仓库只包含：

- 数据格式模板：`assets/templates/diary-book-data.example.json`
- 纯虚构、可复现 Demo：`assets/diary-book/demo/`
- 固定翻页运行时、构建器与本文档。

默认构建器拒绝向仓库公开目录写入真实内容。只有维护公开虚构 Demo 时，才可显式使用 `--public-demo`。

## 输入清单

新建本地私有 `diary-book-data.local.json`，并将其与图谱、头像、海报和输出放在同一日记本目录。例如：

```json
{
  "schemaVersion": 1,
  "book": {
    "id": "life-2026",
    "title": "2026 生活日记",
    "subtitle": "一些普通但值得记住的日子",
    "coverSrc": "assets/cover-fallback.svg",
    "coverImageSrc": "assets/cover-assets/cover-main-3x4.png",
    "coverImageAlt": "原创封面主视觉",
    "coverImagePosition": "50% 50%",
    "coverEyebrow": "OFFLINE DIARY",
    "coverTitle": "纸上小日子",
    "coverSubtitle": "一些普通但值得记住的日子",
    "coverTheme": "brick",
    "graphHref": "character-graph.html"
  },
  "periods": [
    {
      "id": "late-summer",
      "title": "夏末篇",
      "startDate": "2026-08-01",
      "endDate": "2026-08-31",
      "summary": "下雨、晚饭和慢慢变好的日常",
      "coverSrc": "assets/periods/late-summer.png"
    }
  ],
  "entries": [
    {
      "id": "2026-08-28",
      "date": "2026-08-28",
      "periodId": "late-summer",
      "title": "背单词、双周会和三杯鸡",
      "posterSrc": "assets/entries/2026-08-28.png",
      "summary": "一天里的几个小转折。",
      "characterIds": ["aha", "ayan"],
      "tags": ["工作", "晚饭"]
    }
  ]
}
```

字段规则：

- `book.id`、时期 ID 与日记 ID 在各自范围内唯一，只使用字母、数字、`.`、`_`、`-`。
- `coverImageSrc`、新 `posterSrc` 和时期封面建议严格 3:4；历史海报可为严格 9:16，并在预检中标记为 legacy。
- `coverTheme` 只能是 `brick`、`terracotta`、`forest` 或 `blue`；`coverImagePosition` 只能是两个 0–100% 百分比。
- `coverSrc` 保留向后兼容，可作为旧数据封面背景或图片回退资源；新 Demo 不使用深色旧封面。
- 时期必须按时间递增且不重叠；每篇日记日期必须落在其时期内；同一天只允许一篇。
- `characterIds` 必须命中图谱中的实际角色 ID，不能重复。
- 所有资源必须是相对本地路径；禁止绝对路径、`..`、远程 URL、编码后的路径穿越和指向目录外的符号链接。
- 图谱中的每个角色都必须有唯一、完整居中的 1:1 上半身 `avatarSrc`。旧图谱仍可独立使用，但不能进入日记本模式。

## 构建

先在目标输出目录放好图谱、头像、海报和清单，再执行：

```bash
python3 scripts/build_diary_book.py \
  task-output/diary-book/diary-book-data.local.json \
  --graph task-output/diary-book/character-graph.html \
  --output task-output/diary-book/index.html
```

构建器将固定版本的翻页 JS、CSS 与许可证复制到 `runtime/`；日记本可直接用 `file://` 或本地静态服务器打开。`book.graphHref` 必须精确指向与 `index.html` 同目录的 `--graph` 文件。

维护公开 Demo 时：

```bash
python3 scripts/build_character_graph.py \
  assets/diary-book/demo/character-data.json \
  --output assets/diary-book/demo/character-graph.html

python3 scripts/build_diary_book.py \
  assets/diary-book/demo/diary-book-data.json \
  --graph assets/diary-book/demo/character-graph.html \
  --output assets/diary-book/demo/index.html \
  --public-demo
```

## 页面顺序与跳转

书本顺序固定为：封面 → 扉页 → 目录 → 人物介绍 → 只读关系概览 → 每个时期扉页 → 该时期日记 → 索引 → 封底。构建器会补空白页，使每个时期扉页在桌面双页阅读时从右页开始。

- `#entry=<日记ID>` 直接打开某篇日记，例如 `index.html#entry=2026-08-28`。
- 非日记页使用 `#page=<页码>` 同步当前位置；日记页优先同步 `#entry` 并高亮目录/索引/搜索结果。
- 人物卡与关系概览节点使用 `character-graph.html?character=<角色ID>`，图谱会自动选中并居中该人物。

## 验收

构建前或发布前运行：

```bash
python3 scripts/preflight_check.py \
  --graph task-output/diary-book/character-graph.html \
  --book task-output/diary-book/diary-book-data.local.json
```

人工检查：封面具备彩色书皮、撕纸横线纸、装订线和清晰的标题层级；舞台为白纸书页与浅色桌面；全部单页为 3:4；新海报为 3:4，历史 9:16 海报完整 `contain` 显示；时期从右页开始；手机切单页；目录/搜索/`#entry`/阅读进度可用；人物头像完整居中；关系概览不遮挡文字；点击人物可打开并定位独立图谱；无远程资源。
