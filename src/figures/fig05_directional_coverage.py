"""64 点覆盖与圆域边缘朝外的定向源。"""
import numpy as np
from matplotlib.patches import Circle,Wedge,Rectangle
from figures.style import setup,geometry_axes,save,cli

def plot(data,output="outputs/figures/fig05_directional_coverage"):
    if data["problem"]!=4:
        raise ValueError("requires problem 4 result")
    fig,ax=setup()
    nodes=np.asarray(data["coverage"])
    ax.add_patch(Circle((0,0),1800,fill=False,color="black",label="目标圆域"))
    ax.add_patch(Wedge((1800,0),1000,-90,90,facecolor="#F2DFC5",edgecolor="#D49348",alpha=.6,label="朝外发射半圆（示例）"))
    ax.add_patch(Rectangle((1500,-300),600,600,fill=False,edgecolor="#46856A",lw=1.5,label="含目标的网格单元"))
    outside=np.linalg.norm(nodes,axis=1)>1800
    ax.scatter(nodes[~outside,0],nodes[~outside,1],color="#477C99",s=18,label="圆域内节点")
    ax.scatter(nodes[outside,0],nodes[outside,1],color="#B46A70",marker="s",s=22,label="圆域外节点")
    ax.scatter(1800,0,color="#D49348",marker="*",s=100)
    ax.set_xlim(-2400,2950)
    ax.set_ylim(-2400,2400)
    geometry_axes(ax)
    ax.set_title("混合源覆盖：保留圆域外节点以接收朝外信号")
    ax.legend(loc="upper center",bbox_to_anchor=(.5,-.15),ncol=2)
    save(fig,output,"analytic_coverage_with_constructed_edge_source","网格单元四顶点中至少一点处于任意发射闭半平面内")

if __name__=="__main__":
    cli(plot,"outputs/problem4.json","outputs/figures/fig05_directional_coverage")
