"""问题4：混合定向干扰源搜索定位与清除。"""
from legacy_solution.common.search import solve_search
from legacy_solution.common.runner import run_cli

def solve(client, config=None):
    return solve_search(4, client, config)

def main():
    run_cli(4, solve)

if __name__ == "__main__":
    main()
