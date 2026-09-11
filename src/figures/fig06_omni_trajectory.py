from figures.trajectory import draw_trajectory
from figures.style import cli

def plot(data,output="outputs/figures/fig06_omni_trajectory"):
    draw_trajectory(data,output,3)

if __name__=="__main__":
    cli(plot,"outputs/problem3.json","outputs/figures/fig06_omni_trajectory")
