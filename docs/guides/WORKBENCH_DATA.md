# 论文工作台数据说明

## 目录审计

`data/papers.json` 是公开主目录，审计时有 273 条记录，论文 ID 与 DOI 均唯一。底层仍是 JSON 对象数组。下表记录改造前数据中的键和类型，括号内为记录数。

| 覆盖 | 字段 | JSON 类型 |
| --- | --- | --- |
| 273 | `id`、`title`、`journal`、`document_type`、`doi`、`url`、`role`、`summary` | 字符串 |
| 273 | `year` | 数字 |
| 273 | `authors`、`systems`、`methods`、`properties`、`tags_zh` | 字符串数组 |
| 273 | `verification` | 对象，含 `doi`，部分条目另含 `publisher`、`wos`、`sources`（字符串数组）或 `primary_source`、`verified_at` |
| 按记录而定 | `collection`、`difficulty`（各 229），`scope_note`（218），`wos_uid`（127），`publication_status`（112） | 字符串 |
| 按记录而定 | `publication_date`、`publication_date_precision`、`online_date`、`online_date_precision`（各 54），`volume`（48），`issue`（37），`language`（18），`title_en`（5），`article_number`（3） | 字符串 |
| 48 | `pages` | 字符串或 `null` |
| 54 | `author_details` | 对象数组，每项含 `given`、`family` |
| 151 | `protocol_steps` | 字符串数组 |
| 258 | `evidence` | 对象数组，每项含 `claim`、`basis`、`strength` |
| 178 | `relations` | 对象数组，每项含 `source`、`relation`、`target` |
| 205 | `resources` | 对象数组，每项含 `label`、`url` |

工作台按论文 ID 读取题名译文、标签、电池部件、国内团队选读、学习路线和 45 张要点卡。团队地区依据已登记归属或明确的地区字段，未查证时显示「未知地区」。凡软件实际使用情况不明，先查阅原文计算方法或补充材料再补标签。

可在逐篇核对后补入字符串字段 `functional`、`force_field`、`mlip_architecture`，分别用于对比泛函、力场和机器学习势架构。地区可用明确的 `region` 值（`domestic` 或 `international`），并保留团队归属的核验来源。

## 定量证据字段

工作台可读取可选的 `evidence_card.metrics`。每项需要 `label`、`value`、`source`、`locator`，可以添加单位 `unit`、计算或实验条件 `conditions`、对照信息 `comparison`。下面是包含新字段的论文条目片段，内容仅用于演示结构。

```json
{
  "id": "example_paper",
  "title": "论文原题名",
  "evidence_card": {
    "metrics": [
      {
        "label": "迁移势垒",
        "value": 0.22,
        "unit": "eV",
        "source": "原论文 DOI 或公开来源",
        "locator": "第 5 页，图 3b，路径 A",
        "conditions": "晶相和迁移路径 A"
      }
    ]
  }
}
```

依据原论文 PDF 或补充材料录入数值、单位和准确位置。记录对应的晶相、温度、迁移路径与计算设置。若理论和实验条件不同，分别录入并保留差异。无法逐项核对的论文继续使用现有文本证据。原文文件和个人文库索引存于本机。

## 服务边界

GitHub Pages 直接加载公开 JSON。问答页使用同一套本地服务连接与上传流程，保留 `/api/chat`、`/api/agent`、`/api/keywords`、`/api/upload`，以及现有 Health、Capabilities、Papers、Paper Tags、Search Config、Literature、Zotero Links、Methods 和 Local PDF 接口。工作台的个人文库增强由同源回环服务提供。Zotero 映射、正文证据、本地 PDF 与工具 Agent 继续由服务端做访问控制。
