# 当前项目状态

统计日期：2026-10-25。由 `update_project_status.py` 根据实际库、索引与数据集生成。

| 项目 | 实际数量 |
|---|---:|
| 公开精选论文（唯一 DOI） | 247 |
| 2023 年及以后论文 | 134 |
| 已有 WOS UT | 16 |
| QLoRA 训练样本 | 793 |
| QLoRA 验证样本 | 78 |
| QLoRA 测试样本 | 127 |

专题科研问答：40 个，分基础知识、计算流程和常见问题，引用 17 篇库内论文及官方文档，附操作步骤和验收项。

静态导读：247 篇论文 × 4 类，共 988 条；按公开目录整理研究主题、方法标签、范围与阅读路线。

本版本未重新训练模型。训练/验证/测试按论文来源分组隔离；验证集用于选择方案，固定方案后再用测试集评估。

网页发布书目、教学资料与汇总统计；论文正文和 Zotero 私有记录保存在本机。

- [AI 实施指南](AI_BATTERY_APPLICATIONS.md)
- [未来研究方向](BATTERY_COMPUTATION_FUTURE_DIRECTIONS.md)
- JSON 统计：`data/project_status.json`；训练来源与文件 SHA-256：`finetune/data/manifest.json`。
