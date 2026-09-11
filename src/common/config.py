from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    delta_deg: float = 1.01
    disk_sides: int = 128
    clear_radius: float = 19.9
    max_local_measures: int = 8
    max_no_signal: int = 2
    scenario_limit: int = 128
    candidate_shortlist: int = 6
    reserve_seconds: float = 30.0
    seed: int = 20260910
    baseline: bool = False

    def __post_init__(self):
        if not 1 <= self.delta_deg <= 1.01:
            raise ValueError("误差半角须在 [1, 1.01] 内，以保持兜底覆盖保证")
        if self.disk_sides < 16 or not 0 < self.clear_radius < 20:
            raise ValueError("非法几何配置")
        if min(self.scenario_limit, self.candidate_shortlist, self.max_local_measures, self.max_no_signal) < 1:
            raise ValueError("计数配置必须为正")
