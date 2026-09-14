# 人物图库与关系

新图brief的characters使用精确id、name、species和身份anchors，protagonistId不得靠列表首项推断。角色卡与表情按style-system.md及geometry.json构造，每个角色使用自己的物种尺寸。

新角色先以identity-source和--preview生成draft人物形象卡：一张图内清楚展示全身、脸部细节与从输入照片/文字提取的可观察锚点（发型、眼镜、服装、耳尾等），并附固定参考包。用户确认卡片的当前版本后才记录confirmed、approvedVersion和approvedBy=user；之后正式海报直接复用该身份版本，不逐篇重新确认。图谱status=actual仅说明实际数据，不代表用户审批。

图谱兼容assets/templates/character-graph-data.example.json和原build_character_graph.py接口：atlas.src/cols/rows；nodes的id/name/role/col/row/x/y/anchors；edges的source/target/label/type/curve。新节点可带profile：approval 为 draft 或 approved、appearance 为固定外观列表、standardCardSrc 为相对图谱的标准卡图片、firstAppearance 为首次出现的日记说明。右侧详情以“新角色草稿”或“可用于正式成品”展示，避免抽象状态名。图谱anchors仍至少四条；brief允许两条起步，入图库前补齐实际可见特征。不借用模板人物。仅记录用户提供或确认的关系；未说明的关系不画边、不猜标签。

avatarSrc相对HTML；如使用独立头像则每个节点都有唯一1:1头像。旧图谱可回退atlas裁切，新日记本仍要求独立头像。按原接口构建：
```bash
python3 scripts/build_character_graph.py character-data.json --output character-graph.html
```
命令在HTML旁创建`fonts/Yozai-*.ttf`和OFL许可，图谱离线统一使用悠哉字体。图谱浏览/编辑、搜索、拖拽、关系、localStorage与?character=<ID>跳转保持原接口。日记本兼容规则见diary-book-system.md。
