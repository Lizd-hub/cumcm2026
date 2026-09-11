# 2026 数模 B 题：无线电干扰源定位与清除

主解题代码位于 `src/b_solution`，版本为 `v0.3.0`；原始方案完整保存在 `src/legacy_solution`，版本为 `v0.1.0`，用于复现和对照。主方案默认运行独立离线模拟器，官方测试须由用户在模拟器界面启动。分层和依赖方向见 `src/b_solution/ARCHITECTURE.md`。

## 安装

Python 3.11 或以上，在项目根目录执行（Windows PowerShell）：

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest -q
```

Linux/macOS 将解释器路径换为 `.venv/bin/python`。绘图需要 Microsoft YaHei、SimHei、Noto Sans CJK SC 或 SimSun 字体，缺失时明确报错。依赖锁定快照见 `requirements-lock.txt`；该快照来自 Windows/Python 3.14，其他 Python 版本优先使用 pyproject 中的兼容范围。

## 四问独立运行

```powershell
.venv/Scripts/python -m b_solution run --question 3 --seed 20260910 --output outputs/runs
.venv/Scripts/python -m b_solution run --question 4 --seed 20260910 --output outputs/runs

# 旧版问题一、二接口（仅用于复现 v0.1.0）
.venv/Scripts/python -m legacy_solution.solvers.problem1 --input examples/problem1.json
.venv/Scripts/python -m legacy_solution.solvers.problem2 --input examples/problem2.json
```

第一问输入为 `observations: [{position: [x,y], bearing_deg: angle}]`，可选 `delta_deg`；第二问输入单条 `{position: [x,y], bearing_deg: angle}`。省略输入时运行构造示例并标注来源。第一问返回 empty/unbounded/bounded；无界直径在严格 JSON 中编码为字符串 `"Infinity"`。

第三、四问默认离线随机场景。通过 `--scene examples/scene.json` 可读取自建场景，`--baseline` 使用覆盖后直接光学兜底的对照策略。示例 scene 含定向源，应由问题四运行。离线真值只传入模拟器；在线搜索不接触目标数、位置、半径或朝向。

Python 调用接口：

```python
from b_solution.infrastructure import OfflineSimulator, Session
from b_solution.core import Solver

session = Session(OfflineSimulator(20260910), robot_id="offline")
result = Solver(session, mixed=False).run()
```

每次输出 JSON 结果和 JSONL 动作记录；离线运行另写 evaluation.json，真值仅用于事后核验。结果含频道状态、覆盖证书、耗时分解、配置、随机种子、来源和退出原因。零成功清除的平均时间为 null。

## 官方 HTTP 接口

先在官方模拟器中登录，选择正确问题和演练/正式模式，等待界面显示接口已就绪，再运行：

```powershell
.venv/Scripts/python -m b_solution run --question 3 --connect --team-id "实际参赛队号" --session-kind practice --ack-session-start --output outputs/official
.venv/Scripts/python -m b_solution run --question 4 --connect --team-id "实际参赛队号" --session-kind practice --ack-session-start --output outputs/official
```

地址默认 `http://127.0.0.1:32026`，可用 `--base-url` 修改。`--session-kind` 只用于命名运行日志并提醒当前 UI 选择，不控制模拟器模式。正式模式需在界面选择，代码不会启动正式测试，也不会下载、解析或修改官方加密日志。

客户端发送 /enter、/measure、/clear、/exit，逐条等待响应。超时、连接中断、429/500 最多尝试三次，复用原请求和 request_id，退避 0.2/0.5 秒。结果不确定时停止发送新动作。拒绝响应不更新状态；只有有效测向更新测向机频道。虚拟耗时按附件核对，无虚拟检测 sleep。实际时间按 /enter 的剩余预算管理，默认预留 30 秒收尾。

HTTP 原始日志即时追加至 `.raw.jsonl`，已有文件会拒绝覆盖，请每次使用新的输出文件名；其请求内容包含参赛队号，分享前按匿名提交要求处理副本。官方加密日志仍须在模拟器中导出并保留原文件名。

默认测试不会触碰真实模拟器；`tests/test_official_simulator.py` 已覆盖四接口 HTTP 契约。若已在界面中启动可用会话，可显式配置 `CUMCM_OFFICIAL_BASE_URL` 和 `CUMCM_OFFICIAL_TEAM_ID` 后运行 `pytest -m official` 做一次 enter/exit 冒烟检查。正式模式仍以模拟器界面为准。

## 算法与实现约定

- 问题一采用半平面可行性和坐标极值 LP 检查无界性，枚举边界交点及凸包最远点对；固定种子的随机增量最小包围圆由独立支撑点枚举测试核验。
- 定位角域使用正向射线，处理跨零角；理论半角 1°，在线默认 1.01°。接收半径 1000 米不是距离下界。圆域和 1500 米接收圆盘均使用 128 边外接多边形。
- 问题二先按外包络所有顶点检查安全性，再用廉价交会代理排序，精算前 6 个候选。场景含顶点、边中点及 128 个确定性内部点；误差取三点。场景评分不解释为连续最坏情况或概率。
- 离线候选评分固定完成精算，保证同配置的虚拟轨迹可复现；HTTP 每次选点限约 0.2 秒，超时采用已完成评分，尚无精算结果则采用快速代理。在线轨迹可能随计算速度变化。
- 全向使用 16 个网格节点，混合使用 64 个节点，保留圆域外点。只有全部频道 cleared/absent_certified 或清除 16 个目标才声明完整。
- 混合情形不利用无信号排除距离圆盘。外包络半径不超过 19.9 米时清除；局部最多 8 次新测向或连续两次无信号，随后使用 380 点有限光学兜底。
- 默认不根据有限场景采样删减光学兜底点；保底完整性不意味着虚拟耗时最优或一定满足任何网络环境下的现实限时。
- 离线模拟器的均匀圆域采样和固定哈希误差仅是自建实验模型，不能当作官方目标分布与误差场。

## 配对实验与表格

```powershell
.venv/Scripts/python -m legacy_solution.experiments.benchmark
.venv/Scripts/python -m legacy_solution.experiments.summarize
```

默认使用 20260910—20260929 共 20 个种子，对问题三、四分别运行基线和主动定位，共 80 次。每组共享目标真值与误差场，失败案例仍保留。summary.json 保存每次结果；paired_comparison.csv 保存配对差值。现实运行时间随硬件与并发负载变化。

## 两种方案统一环境比较

`legacy_solution` 是保存下来的 v0.1.0 旧方案。下面的命令使用同一个场景生成器、同一组目标真值、同一误差场和同一动作计费规则，比较 v0.3.0 主方案与旧方案；默认同时保留两套方案各自的 active/baseline 变体：

```powershell
.venv/Scripts/python -m legacy_solution.experiments.compare_solutions --trials 10
```

结果写入 `outputs/shared_comparison/`，包括逐案 `raw_results.json/csv`、配对差值、汇总表和中文 `analysis.md`。`random` 为常规场景，`boundary` 为最小接收半径、边界源和定向源压力场景。该比较仍是离线实验，不是官方测试成绩。

正式测试表默认输出缺失状态，绝不使用离线成绩填充。实际取得结果后，准备 JSON 数组并传入 `--formal-records`，每条包含 `problem`、`source: "official_formal"`、`case_code`、`cleared_count`、`virtual_time_s`、`real_time_s` 和 `log_filename`。程序不会核实人工输入的官方成绩，应由队员与原日志核对。

## 九幅独立论文图

先生成四问结果和 benchmark/summary.json，再运行：

```powershell
.venv/Scripts/python -m legacy_solution.figures.fig01_localization
.venv/Scripts/python -m legacy_solution.figures.fig02_circle_counterexample
.venv/Scripts/python -m legacy_solution.figures.fig03_candidate_region
.venv/Scripts/python -m legacy_solution.figures.fig04_omni_coverage
.venv/Scripts/python -m legacy_solution.figures.fig05_directional_coverage
.venv/Scripts/python -m legacy_solution.figures.fig06_omni_trajectory
.venv/Scripts/python -m legacy_solution.figures.fig07_mixed_trajectory
.venv/Scripts/python -m legacy_solution.figures.fig08_time_breakdown
.venv/Scripts/python -m legacy_solution.figures.fig09_trial_distribution
```

每个模块均提供 `plot(data, output)` 和 `--input/--output`；一次生成一幅图的 PDF、SVG、300 dpi PNG，附来源和图意元数据。作图只读取已保存结果，不重新求解。第 3 图绿色边界栅格仅作显示，安全候选标签仍来自连续多边形判定。轨迹中的星号为成功清除位置，不是精确目标坐标。

图表为中文单图结构，几何图等比例坐标；脚本检查文字裁切。导出后仍需目视核查及 PDF 碰撞审核；本次检查记录见 outputs/qa，验证结果摘要见 docs/implementation-validation.md。

## 数据与目录

`outputs/` 为可重建输出，默认不纳入 Git；主包、旧版包、`tests/`、`examples/`、依赖和说明文件应纳入支撑材料。原有题目资料和解题思路文档保持原样。
