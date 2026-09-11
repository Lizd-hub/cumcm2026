"""区域直径不能替代最小包围圆直径。"""
import numpy as np
from matplotlib.patches import Circle,Polygon
from figures.style import setup,geometry_axes,save,cli

def plot(data,output="outputs/figures/fig02_circle_counterexample"):
    d=data["counterexample"]
    fig,ax=setup()
    ax.add_patch(Polygon(d["vertices"],facecolor="#CCE1EB",edgecolor="#477C99",label="等边三角形"))
    ax.add_patch(Circle(d["center"],d["radius"],fill=False,color="#46856A",label="最小包围圆"))
    midpoint=np.mean(d["farthest_pair"],axis=0)
    ax.add_patch(Circle(midpoint,d["diameter"]/2,fill=False,color="#B46A70",ls="--",label="最远点对直径圆"))
    ax.set_xlim(-20,120)
    ax.set_ylim(-65,110)
    ax.set_title(f"反例：区域直径 {d['diameter']:.0f} 米，最小圆半径 {d['radius']:.2f} 米")
    ax.legend(loc="upper center",bbox_to_anchor=(.5,-.15),ncol=2)
    geometry_axes(ax)
    save(fig,output,"constructed","等边三角形最小包围圆半径大于区域直径的一半")

if __name__=="__main__":
    cli(plot,"outputs/problem1.json","outputs/figures/fig02_circle_counterexample")
