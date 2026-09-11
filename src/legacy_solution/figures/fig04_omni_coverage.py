"""16 点全向覆盖证书图。"""
import numpy as np
from matplotlib.patches import Circle
from legacy_solution.figures.style import setup,geometry_axes,save,cli

def plot(data,output="outputs/figures/fig04_omni_coverage"):
    if data["problem"]!=3:
        raise ValueError("requires problem 3 result")
    fig,ax=setup()
    nodes=np.asarray(data["coverage"])
    for q in nodes:
        ax.add_patch(Circle(q,1000,facecolor="#CCE1EB",edgecolor="#477C99",alpha=.10,lw=.6))
    ax.add_patch(Circle((0,0),1800,fill=False,color="black",lw=1.2,label="目标圆域"))
    outside=np.linalg.norm(nodes,axis=1)>1800
    for mask,marker,label in [(~outside,"o","圆域内检测点"),(outside,"s","圆域外检测点")]:
        ax.scatter(nodes[mask,0],nodes[mask,1],marker=marker,color="#477C99",label=label,s=24)
    ax.set_xlim(-2900,2900)
    ax.set_ylim(-2900,2900)
    ax.set_title("全向源覆盖：最近网格点距离不超过 848.53 米")
    ax.legend(loc="upper center",bbox_to_anchor=(.5,-.15),ncol=3)
    geometry_axes(ax)
    save(fig,output,"analytic_coverage","16 个覆盖点保证发现每个未清除的全向源")

if __name__=="__main__":
    cli(plot,"outputs/problem3.json","outputs/figures/fig04_omni_coverage")
