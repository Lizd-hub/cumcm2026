from legacy_solution.figures.trajectory import draw_trajectory
from legacy_solution.figures.style import cli

def plot(data,output="outputs/figures/fig07_mixed_trajectory"):
    draw_trajectory(data,output,4)

if __name__=="__main__":
    cli(plot,"outputs/problem4.json","outputs/figures/fig07_mixed_trajectory")
