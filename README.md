# 选岗参谋 · M0 最小闭环

公务员考试选岗决策 Agent 的后端核心：**职位表解析管线 → 确定性资格规则引擎 → 匹配 API**。
设计红线：资格判断链路 LLM 零参与；任何无法判定的条件输出 UNCERTAIN（存疑），绝不假阳性 PASS。

> **数据现状（2026-11-20）**：已接入 **江苏省2027年度省考真实数据**（5768 个岗位 + 官方专业参考目录 + 2024-2026 历史进面线）。
> 另保留一套仿真演示数据（2026 场次）供回归测试与离线演示。
> ⚠️ 真实数据未含公安机关人民警察职位（单独简章发布）；所有岗位 parse_status=auto，报考前务必以招录单位审核为准。

## 快速开始

```powershell
pip install -r requirements.txt
python scripts\import_real.py     # 导入真实2027省考数据（幂等，约30秒）
python scripts\run_real.py        # 真实数据 × 三画像匹配演示（约1秒）
python scripts\run_demo.py        # 仿真演示数据（离线可用）
python -m pytest tests -q         # 64 条回归测试（资格引擎 CI 门禁）
python -m uvicorn app.main:app --port 8765   # 启动 API + 演示页 http://127.0.0.1:8765
```

## 真实数据来源（data/real/）

| 数据 | 来源 | 说明 |
|---|---|---|
| 省级机关/13设区市/监狱戒毒系统职位简介表 | 官方原件（南京为市委组织部 xlsx，其余为官方 xls 镜像） | 2027年度，共 5768 岗 |
| 专业参考目录 | 省委组织部官方 doc（jszzb.gov.cn，已转 docx） | 50 大类 × 研究生/本科/专科三栏，4763 条 |
| 2024-2026 进面分/报名人数 | 华图汇总（原始为官方公示） | 按「地区+单位+职位」11位代码关联，单位名+职位名双重校验，5200 条 |
| 考试日程 | 省政府官方公告 | 报名 2026-11-03~11-09，笔试 2026-12-06 |

真实目录代码为合成编码：层次(1研究生/2本科/3专科)+大类序号(3位)+专业序号(2位)，
前缀即祖先关系，与引擎原有代码前缀匹配逻辑兼容；「本科及以上」职位自动允许研究生/本科两栏同名大类。

## 目录结构

```
app/
  models.py            # SQLAlchemy Schema（exam/position/score_line/major_catalog/audit_case/user_profile/reg_stats）
  engine/
    conditions.py      # 三态条件树引擎（AND/OR + 学历/学位/应届/党员/户籍/基层/证书）
    major.py           # 专业匹配：精确→目录祖先→审核口径案例→UNCERTAIN
    matcher.py         # 画像×岗位批量匹配
  pipeline/
    excel_parser.py    # 省份模板(YAML)驱动的 Excel 列映射
    cond_extract.py    # 确定性条件抽取（LLM 辅助为可插拔扩展点，输出须人工审核）
    importer.py        # 导入编排（parse_status=auto 待审核）
  api/routes.py        # /api/match /api/positions/{id}/card /api/import 等
  static/demo.html     # 演示前端（画像表单→三色匹配→岗位情报卡）
config/provinces/      # 省份列名映射模板（新省份=新增一份 YAML）
scripts/               # 种子数据 / 仿真职位表生成 / 端到端演示
tests/                 # 50 条回归用例
```

## 关键设计

- **三态逻辑**：AND 中 FAIL 优先、其次 UNCERTAIN；OR 中 PASS 优先。画像字段缺失一律 UNCERTAIN。
- **性别硬性条件**：人民警察等职位「男性/女性」为硬条件（gender 字段），画像缺失 → UNCERTAIN；「适合男性」仍仅为风险提示。
- **学位派生**：真实表无学位栏，「取得相应学位」按学历栏派生（本科→学士/研究生→硕士）；「本科阶段须为XX类专业」等阶段限制 → 人工审核。
- **视力/体能/定向身份**等无法自动判定的条件一律 manual_review → UNCERTAIN，绝不假阳性 PASS。
- **专业目录**：教育部本科目录真实代码（0809 计算机类 / 1201 管理科学与工程类…），代码前缀即祖先关系。
  经典陷阱已覆盖：信息管理与信息系统 报 计算机类 → FAIL（附所属类别说明）。
- **审核口径案例库**（audit_case）：旧专业名、争议口径按历史案例判定并附依据——这是持续积累的数据壁垒。
- **风险≠硬条件**："适合男性/夜班/下乡"只进 risk_flags 提示，绝不导致 FAIL；"最低服务期5年"同时提取为结构化字段+风险标签。
- **三不限识别**：专业不限且无身份/户籍/基层等硬限制 → 自动打"竞争极高"标签。
- **数据库**：开发默认 SQLite，设 `DATABASE_URL=postgresql+psycopg://...` 即切 PG，无需改代码。

## API

| 端点 | 说明 |
|---|---|
| POST /api/match | {exam_id, profile} → 三色匹配结果+逐条理由+风险标签 |
| GET /api/positions/{id}/card | 岗位情报卡（原文条件+历史进面线+免责声明） |
| POST /api/import | 上传职位表 Excel + 省份模板名 → 解析入库 |
| GET /api/exams, /api/positions | 场次/岗位列表 |
| POST /api/profiles | 持久化用户画像 |

## 下一步（M1）

- [ ] 接百炼 API：对话编排层（function calling 调 match/card/chance 工具）+ 回答数字忠实度校验器
- [ ] LLM 辅助条件抽取 + 人工审核队列界面
- [ ] 进面概率 V1（历史分位数规则）
- [x] 真实省份数据接入（江苏2027职位表+官方专业目录+近3年进面线，2026-11-20）
- [ ] 公安机关人民警察职位表接入（单独简章）
- [ ] 条件抽取人工审核队列（当前 5768 岗均为 auto 待审核）
- [ ] 小程序前端（Taro）替换演示页
