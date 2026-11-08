# 论文与汇报绘图

图形使用 ReportLab、fontTools 与 matplotlib 生成矢量 PDF；论文的中英文图作为编译输入保存在 `overleaf/figures/`，PPT 图保存在 `slides/figures/`。以下路径相对仓库根目录。

## 构建与依赖

```bash
python3 -m pip install -r tools/figures/requirements.txt
make figures                       # 包括群体、RelBench 累计和机制图
python3 tools/figures/build.py architecture  # 只画一幅
python3 tools/figures/mechanism.py  # A/B/C 中英文图及数值宏
python3 tools/figures/build.py --out /tmp/mavra-figures  # 主绘图器输出到预览目录
make deck-figures                  # PPT 的六幅图，生成 PDF 并转 PNG
```

数据图使用 Matplotlib 直接输出带嵌入字体的矢量 PDF，无需 TeX Live 或 Ghostscript。英文优先使用 Times New Roman，其次为 Liberation Serif、DejaVu Serif；中文需要系统安装 SimSun 或 Noto CJK 等字体。示意图仍需带 `kpsewhich` 的 TeX Live 及 libertine、inconsolata、fandol 字体，中文示意图使用 Noto Sans CJK SC。PDF 预览和 PPT 的 PNG 转换需要 Poppler 的 `pdftoppm`。Python 依赖清单用于建立绘图环境，未声明为历史实验环境锁文件。

论文编译直接使用已提交的 PDF，无需绘图环境。`make figures` 调用主绘图器、`population.py`、`relbench_cumulative.py` 和 `mechanism.py`；各自保留现有接口。

## 图形与数据来源

| 输出名（均有英文与 `-zh` 中文 PDF） | 脚本 | 数据或来源 |
| --- | --- | --- |
| `metric-record` | `metric_record.py` | 图 1 动机图（单栏，沿用原版样式：LLM 智能体图标、工作台窗口、请求流、共享数据库）。上半：10-01 工作负载轨迹（`exp/2026-10-01-workload-characterization/`）中三个只给指标名称的电子品类营业额会话 s094、s073、s091；虚线大框框住全部 20 个会话都重复的第 1–4 步（list tables / read sales / item / date table），第 5 步是各会话自己的做法（试 3 个营业额列 / 给 12 个月排序 / 比较两年）；脚本逐条核对调用与 SQL 片段，会话数取自 `gen/workload-example.tex`（`tools/workload-stats.py --example M5`，需 pglast）。下半：这些 SQL 连接 item 时没有当前行条件，ETL 装载商品历史版本后（与图 2 相同的商品 17）同一 SQL 把它算两次 |
| `running-example` | `example.py` | 优化实验的学习、使用与修复轨迹，来源见脚本文件头 |
| `architecture` | `architecture.py` | 系统示意 |
| `extraction` | `extraction.py` | 第 IV-B/C 节单栏图（84.6 × 49.0 mm）：发布时定义怎样从会话得到、条件怎样从实现派生。上方是智能体 1 经核验的会话 SQL，`i_category = 'Electronics'` 标为定义过滤 φ，`d_year = 2001 AND d_moy = 1` 标为期间参数 p，两支箭头分别指向连接树里的 item（φ 作为固定过滤）与 date_dim（d_year、d_moy 成为虚线参数槽 p），即 G3 的拆分（`metric::check_filter`）。中间把 I 画成列级连接树：表头灰条、钥匙标出键列、鸦爪线表示 N:1 连接（多端在事实表，一端是维表键），灰色圆标 1–5 把派生条件钉在各自守护的列或边上（粒度、连接基数、连接完整性、日期映射、日期覆盖，同 `bound_conditions`）。下方按判定规则分两组：KeyUnique 要求行数 = 键数（10⁶、1,000、1,096）；Unmatched 用量规表示：填充为发布时测得的未匹配比例即基线 b（0.00%、1.03%），其上浅蓝窄带是 +0.1 个百分点的容差，红线为界限，红色区为不通过。紫色描边标签 G1–G7 标在各检查作用的位置；最下方条形图在同一刻度上比较 G6、G7 复现的 2,754,299.60 与缺 φ 的草稿 13,532,799.00（约 5 倍）。数值由 `src/metricbench.rs` 的确定性测试数据算出，并与 `exp/2026-10-08-lifecycle/cell-mavra.json`（orphan_ratio 0、time.loss_ratio 0.010305）及 `exp/2026-10-31-diverse-scenarios/case-evidence.json`（10,305 行无日期、G7 值）核对 |
| `maintenance` | `maintenance.py` | 第 IV-D 节单栏图（84.6 × 50.2 mm）：上半是“条件 × 定义”共享矩阵：维护实验的四个定义（门店营业额 SR、退货金额 RA、退货率 RR、电子品类营业额 ER，即 `integration_tests.rs` 的 M1/M2/M3/M5）对 7 条检查结果共 15 处引用；行首圆标 1–5 与图 3 相同，钥匙表示 KeyUnique、小量规表示 Unmatched；同一行的圆点用线连起来，表示一条结果服务这些定义（date_dim 键检查四个定义共用；store_returns 键检查同时是 RA 的粒度与 RR 的连接基数）。闪电标出两种写入，循环箭头标出各自重跑的条件；底行方块计数：实心为对全部智能体只跑一次的检查，空心为整定义重查才多跑的检查（item 载入 2/5，销售追加 3/12）。下半是受限修复：item 键检查 1001 行 / 1000 键（1 < 比值 < 1.5 才尝试），候选为不同取值 ≤ 20 的非键列；条形图画每个取值的行数，虚线是不同键数 1000，只有条形恰好到线的取值才进入验证：`i_is_current = 'Y'` 过滤后 1000/1000，唯一通过；'N'（1 行）与 5 个类别（200–201 行）被剪枝；`i_current_price`（50 个取值）划掉不尝试。结果存为 `grain:item`，回归后发布连接与指标修订版 1（`repair_grain`、`restricted_repair`）。测试数据中 item 1000 行、5 类各 200、i_current_price 50 个取值，运行示例加商品 17 的一行历史（电子类 201 行） |
| `snapshot` | `snapshot.py` | 第 IV-E 节单栏图（84.6 × 47.0 mm）：上方是执行前准入（算法 2 第 2 行，L2 标签）的三种结果，请求画成接口调用胶囊：声明当前修订 r1 通过并在 s′ 中执行；声明已失效的 r0 被拒并给出当前修订（`check_metric_refs`）；缺 `i_is_current = 'Y'` 的 SQL 被 `grain:item` 拦下（`review_sql`）。中间是一条时间轴：ETL 写事务的框里同时画出 `mavra_versions` 中 item 的 16 行计数器（16 个小格，pid%16 = 5 那格加 1），表示计数与数据同一事务提交；智能体 2 的快照 s 在提交前读到 item = 0、复用结论、看不到提交；步骤 6 的维护与修复检查在快照之外运行，画成“读 v=1 → 检查 → 读 v=1 = 记录”，即 `exec_check` 前后两次 `tx_now` 相同才写入；修复后智能体 N 的快照 s′ 读到 item = 1 并复用修复检查写下的结论。下方是按 id(c)@v_s 存放的 H_tx，每行一条完整的键，标出写入者（发布、维护、修复）与复用它的快照。版本（快照读到的 item=0/1 与键里的 @item=0/1）一律青色，便于对应 |
| `replay-outcomes` | `replay_outcomes.py` | 验证缓存、TPC-DS 和通用性回放 |
| `maintenance-cost` | `maintenance_cost.py` | `exp/2026-10-02-cache-baseline-tpcds/cb-1m-share-stats.json` |
| `scenario-changes` | `scenario_changes.py` | `exp/2026-10-10-scenarios-q5/` |
| `two-schemas` | `two_schemas.py` | `exp/2026-10-31-diverse-scenarios/study-stats.json`；六个冻结基线对照、两格修复后原生重跑及四方法共同的跨智能体新题；三指标、四题型、十一类变化，13 情形等权，单栏 84.6 × 55 mm、32 根柱；一轮／方法，不画误差棒 |
| `consumer-cost` | `consumer_cost.py` | 合成场景 `holdout-cost.json` 与通用性 `e2e/outcomes.json.gz` |
| `population` | `population.py` | `exp/2026-10-12-population/population-stats.json`；84.6 × 74 mm 单栏、两行两列，保留四个面板及运行范围误差线 |
| `relbench-cumulative` | `relbench_cumulative.py` | `exp/2026-10-20-relbench/paper-sessions.json` |
| `memory-access-pilot` | `mechanism.py` | `exp/2026-10-29-mechanism-pilot/pilot-summary.json`，八格开发预实验 |
| `fixed-sharing` | `mechanism.py` | 同批 `system-summary.json` 的 B：固定定义数的三轮共享对照，两个到达模式的数据库耗时；验证 SQL 次数在正文报告 |
| `snapshot-control` | `mechanism.py` | 同批 `system-summary.json` 的 C，以及 10-02 批次的 `snapshot-binding-stats.json` / `snapshot-binding-shards-stats.json`；新因果对照与归档开销分开呈现 |

具体哪些图进入稿件，由 `overleaf/sections/` 和图形包装 `.tex` 的引用决定；不使用固定图号来标识脚本。`baselines.py` 是保留的辅助图，不包含在 `make figures` 中；早期外部记忆基线的采用范围以 RelBench 协议为准。

## 汇报图

`build.py --deck` 绘制 `structure`、`definition`、`process` 三张机制图，以及 `run-publish`、`run-use`、`run-maintain` 三张过程图，只生成中文版。共用组件在 `parts.py`、`deckparts.py`，配色在 `deckpal.py`。这些脚本和论文绘图共用工具，输出到 `slides/figures/`；PPT 生成与版本说明见 [slides/README.md](../../slides/README.md)。

## 数值核对

数据图读取 `exp/` 中的归档，并按各脚本的实现与 `overleaf/gen/` 宏交叉核对。场景题集、重复轮次和采用的运行必须一致；更新数据时先检查 [实验索引](../../exp/README.md) 和 [论文说明](../../overleaf/README.md)，再重算宏和图形。

方法颜色从 `overleaf/preamble.tex` 读取；图注、标签与 `Description` 在各图对应的 `.tex` 中维护。单图尺寸以脚本内的 `W`、`H` 为准。

## 怎么画出来的

**底层函数**（`vecfig.py` 的 `Sheet`）：坐标单位是毫米，原点在图的左上角，按印刷尺寸画（单栏 84.6 mm，通栏 178 mm）。

第 IV 节的三幅单栏图（`extraction`、`maintenance`、`snapshot`）共用 `smallparts.py`。2026-11-08 按导师意见（原图“看着没有技术含量”，参考 TVA（VLDB 2026）图 3–5 说明数据怎么存）先改为存储结构图；同日又按作者要求（“要讲清楚论文里面没讲清楚的，而不是翻来覆去讲一个东西，信息量要变大”）改为每幅图讲一个正文没有展开、只在代码里的机制，三幅图之间不重复：图 3 讲条件怎样从连接树派生、发布时怎样测出基线与 G1–G7 各查什么；图 4 讲检查结果在定义间的共享、写入后只重跑哪些条件、修复怎样搜索并只接受唯一候选；图 5 讲执行前准入、事务性计数器，以及快照之外的检查在什么条件下才写入 H_tx、哪个快照复用哪条结论。图中的键、版本戳、计数与统计量都取自代码与确定性测试数据，能核对到实验记录的数值写在上表来源里。配色约定：目录条目浅蓝标题条，检查结果存储 H、H_tx 深蓝标题条，数据库中的表（图 3 连接树中的表）灰色标题条，修复用青色；视觉元素沿用图 2：步骤圆标（学习 1–2 紫、执行 4 橙、数据变化与维护 5–6 青）、L$n$ 标签对应算法行号、灰色圆标 1–5 表示派生条件；结果只用红（错误或过期）、蓝（MAVRA 的结果）两色。表格内代码 5.4 pt（印刷约 5.7 pt），列头 5.3 pt；数学撇号用“斜体 s + 文字撇号 ′”，MathText 的 $s'$ 会画成离得很远的小撇。同日第三版按作者意见（“文字是不是稍微有点多……ui 可以稍微丰富一点，但不是为了加而加，而是有意义”）把说明文字换成承载信息的图形：图 3 用列级连接树（钥匙、鸦爪线、φ 实心标签与 p 虚线槽）、Unmatched 量规与答案条形图，G1–G7 改为标在作用位置的紫色描边标签；图 4 用钥匙/量规图标代替条件类型名、连线圆点表示共享、循环箭头表示重跑、方块计数表示省下的检查，修复改为“各取值行数对键数线”的条形图；图 5 把计数器画成 ETL 事务框内的 16 个小格，维护检查画成前后两次读计数，删去单独的计数表。这些图形由 `smallparts.py` 的 `key_icon`、`gauge`、`units`、`bolt`、`rerun`、`crow`、`one_bar`、`db_table`、`gate` 绘制，三幅图共用，含义保持一致。三幅图合计比第二版矮 12.4 mm。图中不得有文字或线条互相压住，宽度由 `text(..., width=)` 断言把关。

```python
rect(x, y, w, h, fill, stroke, sw, r, dash)   # 矩形，r 为圆角
poly(points, fill, stroke, sw)                 # 多边形或折线，立体面用它画
line(x1, y1, x2, y2, stroke, sw, dash)         # 直线
curve(p0, p1, p2, p3, stroke, sw)              # 三次贝塞尔曲线
route(points, stroke, sw, heads, dash)         # 直角折线，拐角为圆角，heads='end'/'both'/None
marker(x, y, kind, size, fill, stroke)         # 数据点：circle / square / triangle / diamond
text(x, y, '文字 $数学$ `代码`', size, fill, style, align, width)
Scale(d0, d1, p0, p1)                          # 数据值到毫米的线性映射
```

**示意图文字转成轮廓**，PDF 不嵌入字体，pdfLaTeX、XeLaTeX 和各种阅读器里显示都一样，也不会出现投稿系统拒收的 Type 3 字体：

- 普通文字用 fontTools 排版，字体与论文一致：Linux Biolinum（标签）、Inconsolata zi4（反引号里的代码，同 `\code`），按 GPOS 表做字距调整；中文落到 Noto Sans CJK SC。中文标签里不要用“……”（会取到西文省略号），写“等”。
- `$...$` 里的数学用 matplotlib 的 MathText 排版，字母用 Libertine（与正文的 newtxmath 一致），缺的符号用 STIX。数学和普通文字共用基线，一个标签里可以混排。
- `text(..., width=...)` 给出可用宽度时，标签超宽会直接报错，改布局不会悄悄把字挤出框。

**共享设置**（`style.py`）：颜色、方法名称、`gen/` 宏的读取与核对，以及 `build()`（每幅图写英文和中文两份）。架构图脚本提供 `NAME`、`W`、`H` 和 `draw(sheet, lang)`。

**数据图**（`mplstyle.py`）：数据图脚本提供 `NAME`、`W`、`H`（毫米）和 `figure(lang)`，返回一个 Matplotlib Figure；`mplstyle.setup(lang)` 设置衬线字体、白底、黑色完整坐标框、向内刻度与普通字重的图例。`mplstyle.save()` 直接保存矢量 PDF，以 `pdf.fonttype=42` 嵌入字体并保留可检索文字。字体大小按单图的印刷尺寸设置；标签通常为 7.5 pt，刻度 7 pt，紧凑图例和分类标签最低 6.5 pt。

## 想改的话

| 想改什么 | 改哪里 |
| --- | --- |
| 某个标签的文字 | 各脚本里的 `LABELS` / `TEXT` 字典，`en` 与 `zh` 各一份 |
| 方法名称或颜色 | 名称在 `style.py` 的 `METHODS`；颜色改 `preamble.tex` 的 `\definecolor`，图和表一起变 |
| 架构图的模块位置 | `architecture.py` 中的 `ADM`、`STORE`、`MAINT`、`LOOKUP`、`EXEC` 坐标；版式以 2026-10-07 最终版为基线，数据库标签固定为 `DataBase` |
| 数据图的方法与顺序 | `replay_outcomes.py` 的 `ROWS`，`maintenance_cost.py` 的 `SERIES`，`scenario_changes.py` 的 `ROWS`（9 种方法，按表 2 分组）与 `MAINTAINERS`（右侧每次运行的失效与修复数） |
| 结果矩阵的情形简称、分组与过期阈值 | `scenario_changes.py` 的 `TEXT`、`GROUP` 与 `STALE` |
| 图的尺寸 | 各脚本的 `W, H`（单栏图宽用 `style.COLUMN`） |

改完运行 `build.py`，再编译论文看效果。图里的含义变了，要同步改 `overleaf/figures/<名称>.tex` 里的图注和 `\Description`。实验数据更新后，先按 `overleaf/README.md` 重新生成 `gen/`，再重建图；核对不通过说明图和正文用的不是同一份数据。

## 当前正文实验图的样式

正文中的 `population`、`relbench-cumulative`、`consumer-cost` 和 `two-schemas` 使用常规折线图或分组柱状图。方法颜色沿用 `preamble.tex`，与表格一致；线型、空心标记、黑色柱框和纹理提供额外区分。图例文字统一为黑色、普通字重，各方法采用相同线宽，不单独加粗 MAVRA。

- 群体代价：三幅折线图，均值曲线加每个智能体位置的最小值--最大值误差线；每题 token 面板保留对数轴。正确率移至图注。
- RelBench 累计 token：每个数据库一幅折线图，用竖直虚线分隔截点，学习与复用阶段在图注解释。
- 留出查询代价：时间和 token 分成两个分组柱状图，柱高是合并全部问题后的均值，误差线覆盖各次运行的均值。
- 两种模式的正确率：使用 10-31 SQL 审查／语义保留修复并统一反馈后的完整单轮批次，比较 ACE、AWM、G-Memory 与完整 MAVRA。两库各三指标，按留出、正常更新、覆盖变化及全部情形分组，共 32 根柱，从零起画；各情形等权，本批一轮不画误差棒。ACE/AWM 为发布组件的 SQL 适配，G-Memory 使用官方核心；旧自制场景对照的归档保留。

2026-10-28 的官方 API 重构见 [实验协议](../../exp/2026-10-28-official/README.md)。新的 Fig.5 将解释智能体工具调用的组成，另用表格计入内部记忆开销；只有完整配对结果通过核对后才替换原 `consumer-cost`，不能将开发或未完成运行当作正式图表。

这些误差线表示运行范围，不是置信区间。图注和 `Description` 必须与图形一起更新；原始数据、宏核对以及统计汇总逻辑不因样式修改而变化。每幅图同时生成英文和中文版本，并以实际单栏或通栏尺寸检查文字、图例和留白。

## 2026-10-29 三幅机制图

`mechanism.py` 同时生成上述 A/B/C 的中英文矢量 PDF 及 `overleaf/gen/mechanism.tex`，来源哈希保存至 `exp/2026-10-29-mechanism-pilot/paper-integration/figure-sources.json`。A/B 为 84.6 mm 单栏图，C 为 178 mm 通栏图；图注在各自 `.tex` 中维护。所有标签不小于 6.5 pt。

论文版本去掉预览页的总标题与长脚注，把实验范围放入图注和正文；先前 `output/mechanism-pilot-20261029/` 的审阅图不覆盖。A 的缺失方案不画 AUC 零值、仍保留 token；B 的三轮误差线保留 96 次查询异常格；C 分开受控正确性与归档读写开销。数字与限制不因排版而改变。
