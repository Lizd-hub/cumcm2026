# 源代码布局

主方案为 `b_solution`（`v0.2.0`），已从原根目录方案迁入此处；运行入口为
`python -m b_solution.run`，官方模拟器连接通过 `--connect` 显式开启。

原先的 `common`、`solvers`、`experiments` 和 `figures` 已整体迁入
`legacy_solution`（`v0.1.0`），只用于旧版复现、图表和公平对照，不再作为默认主方案。

官方接口契约测试位于 `tests/test_official_simulator.py`；真实模拟器冒烟测试只有在
显式设置 `CUMCM_OFFICIAL_BASE_URL` 和 `CUMCM_OFFICIAL_TEAM_ID` 后才会运行。
