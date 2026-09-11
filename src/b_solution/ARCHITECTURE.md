# 代码架构

`b_solution` 按依赖方向拆分为四层：

```text
cli ──────────────┐
reporting ────────┼──> core
                  └──> infrastructure
```

- `core/`：几何算法、覆盖模型和在线求解策略，不负责命令行或文件输出；
- `infrastructure/`：官方 HTTP 协议、本地模拟器和会话状态；
- `cli/`：运行、基准测试、验证和日志预处理命令；
- `reporting/`：绘图与 Word 报告构建，依赖可选的 `report` 依赖组；
- `results/`、`figures/`：随仓库保存的固定复现实验材料，不属于运行时输出。

新代码应从上述子包导入。包根目录保留的 `solver.py`、`protocol.py` 等文件只是
v0.2 导入路径的兼容门面，可在后续主版本升级时统一移除。

推荐通过统一入口执行：

```powershell
python -m b_solution validate
python -m b_solution run --question 3 --seed 0 --output outputs/runs
python -m b_solution benchmark --cases 12 --output outputs/benchmarks
```
