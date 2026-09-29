# 当前参考与组件复用

旧海报补充元素遵循 `poster-revision.md`：已批准不等于符合当前画风，复用前必须核对当前人物/物种参考；旧图只能提供事实与构图。不得让历史资产覆盖当前画风。

默认人物母版为 `assets/style-reference/style-lock-v1/master-approved-v2.png`，风格版本为 **style-lock-v2**。目录名保留是为了兼容已有资源路径，不代表仍使用旧画风。批准范围是12人样貌与体形画法，不是替用户批准真实身份或所有新动作。

当前公开动作示例索引为 `assets/style-reference/style-lock-v1/action-library-v3.json`。人物走路、读书已按新版母版重绘，状态为 draft；猫狗沿用之前的细腿物种素材。公开演示可以用 `load_action(id, preview=True)` 合成；正式复用仍需相应角色和动作获用户批准。维护更新或一次母版批准不能自动把新动作标成 user-approved。

运行 `python3 scripts/build_action_trial.py --output-dir task-output/action-preview` 查看当前动作和海报。源图、母版和动作都有哈希校验；只等比缩放与平移，不镜像、不拉伸、不重画脸。示例角色只用于画法展示，不能冒充用户身份。动作不存在时按原文生成，不改写事件迎合素材。

旧 `components-v1.json`、`action-library-v1.json`、`action-library-v2.json` 和旧整页模板为历史归档，不能作为新任务的人物风格附件。旧组件脚本默认转到当前示例，只有显式 `--legacy` 才复现历史版。旧用户日记和已确认身份不自动重绘；新任务先校准用户角色，再生成。

新动作使用内置生图工具，实际附上当前母版和该角色参考。保留生成 alpha、内部白色与透明安全边，不能全白抠图。文字按实际墨迹中心定位。新图须查看，但不引入自动风格评分或循环重生，也不声称新生成能逐像素锁脸。
