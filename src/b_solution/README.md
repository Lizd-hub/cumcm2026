# 2026 B 题完整建模与复现说明（v0.3.0）

本包对应上传题目《无线电干扰源的快速自动定位与清除》。数值结果来自独立编写的本地模拟器，不是官方演练或正式测试。策略只读取四个接口的反馈，不读取官方隐藏源数据。本包只面向题设模拟环境。

## 先运行一个例子

需要 Python 3.10 或以上。在解压目录打开终端后执行：

```bash
python -m pip install -e ".[test]"
python -m b_solution validate
python -m b_solution run --question 3 --seed 0 --output outputs/runs
python -m b_solution run --question 4 --seed 0 --output outputs/runs
```

`--baseline` 切换基础策略。默认输出在项目目录的 `outputs/runs` 下；可用 `--output` 指定绝对路径。路径含空格时请用引号包住。Windows 的 Python 代码路径推荐 `Path(r"D:\建模\B题")` 或 `Path("D:/建模/B题")`。不要把压缩包内部路径当作已经解压的文件路径。

## 复现报告中的比较

```bash
python -m b_solution benchmark --cases 12 --output outputs/benchmarks
```

每问使用 12 个常规场景及 4 个联合压力场景，两种策略使用相同种子及相同场景参数，共 64 次运行。已有结果在 `results` 中。虚拟时间应在浮点容差内重复；真实运行时间随电脑而变化。JSON 中的 `case_sha256` 是自建场景参数摘要，绝不是官方案例编码。

常规场景的位置按圆域面积均匀抽样，半径在 1000 至 1500 米均匀抽样；这些是自建实验的假设，不是官方分布。空间误差使用有界确定性正弦场，同一地点重复测量不改变误差。压力场景将源放在半径 1800 米的边界上，接收半径取 1000 米，误差取正负 1 度，定向源朝区域外。第四问保持全向和定向源同时存在。

## 在自己的电脑连接官方模拟器

1. 按附件 1 安装并登录官方模拟器，完成服务器时间校验。
2. 选择正确的问题及演练模式，确认界面已经显示接口就绪。
3. 用自己的参赛队号替换下方示例。程序不接收登录密码。

```bash
python -m b_solution run --question 3 --connect --team-id YOUR_TEAM_ID --session-kind practice --ack-session-start --output outputs/official
```

第四问改成 `--question 4`。API 本身不返回当前是演练还是正式模式，命令行标签不能替代界面检查。只有在充分演练且明确决定使用正式机会时，才由参赛者把 `--session-kind` 改为 `formal`；程序会进入当前已经启动的那一局。交付过程未连接官方模拟器、未登录、未消耗正式机会。

请求串行发送；默认连接 `http://127.0.0.1:32026`，也可通过 `--base-url` 覆盖。超时重试复用同一 request_id 和完全相同的请求体。`/clear` 不改变接收机频道；`accepted=false` 的时间零值不覆盖上次有效时刻。不需要为虚拟检测时间额外 sleep。程序保留 JSONL 行为记录，但它不能代替模拟器导出的加密日志。正式日志必须由模拟器导出，保持原文件名。

第三、四问各需三次官方正式测试。报告中的正式结果状态为未运行，不可拿本地数据填写正式成绩。按上传附件，2026 年 9 月 13 日北京时间 17:30 后不能新开测试，建议在 15:30 前完成；执行前请以当前模拟器提示为准。

## 文件说明

| 文件 | 作用 |
|---|---|
| core/geometry.py | 半平面交会、空集与无界判别、旋转卡壳、最小包围圆、第二点接收候选区 |
| core/solver.py | 第三问七点覆盖、第四问三角网格覆盖、滚动动作选择及有限光学覆盖 |
| infrastructure/protocol.py | 四接口、串行通信、幂等重试和截止时间处理 |
| infrastructure/offline_simulator.py | 独立本地仿真和事后评估，不能代表官方模拟器 |
| cli/ | 单次运行、基准实验、验证和日志预处理命令 |
| reporting/ | 可选的绘图和 Word 报告构建工具 |
| matlab/preprocess_jsonl.m | MATLAB 日志预处理对照代码，当前环境未执行 |
| report.md | 中文讲解报告源稿，包含可编辑的 LaTeX 公式 |
| results | 已运行的本地结果、场景示例及验证记录 |
| figures | 报告中的可复现图表 |

## 数据预处理

```bash
python -m b_solution preprocess "outputs/runs/某次运行.jsonl" --output outputs/runs/audit.json
```

保留原日志。仅在统计视图中合并同一 request_id 的幂等返回；不同 request_id 的同地点重复动作仍产生时间费用，不能删掉。`near` 和 `no_signal` 分支不含示向度，这是协议规定，不是待均值填补的缺失数据。MATLAB 对照调用：

```matlab
addpath('matlab');
[T, audit] = preprocess_jsonl("D:/建模/B题/outputs/runs/example.jsonl");
```

MATLAB 对照需要 R2020b 或更高版本。主要求解器和实测验证在 Python 下完成。

## 实现范围和改进边界

保证来自连续几何证明：覆盖站能发现每个源，正读数得到的外包可行域保留真源，有限光学覆盖能清除已经发现的源。滚动选点和就近路线用于减少时间，不保证全局最短。有限情景前瞻只评估部分候选状态，不等于对所有误差的连续最坏情况优化。

当前程序对 `no_signal` 保留历史正读数可行域，避免因未知方向而错误删点。联合位置和发射轴的集合估计可进一步利用负读数，但尚未实现。达到现实截止时间或收到矛盾反馈时程序输出失败记录，不能声称已清除所有目标。

`reporting/make_figures.py` 和 `reporting/build_report.py` 是报告制作脚本；使用 `pip install -e ".[report]"` 安装 python-docx、PyMuPDF、Pillow、Matplotlib 等可选依赖。`reporting/native_math.py` 生成原生可编辑的 Word 公式。这些不是运行定位算法的依赖；基础依赖统一由项目根目录的 `pyproject.toml` 管理。
