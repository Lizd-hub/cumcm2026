"""安全区域及第二检测点；栅格仅用于区域显示。"""
import numpy as np
from matplotlib.patches import Polygon
from figures.style import setup,geometry_axes,save,cli,source_label

def plot(data,output="outputs/figures/fig03_candidate_region"):
    fig,ax=setup()
    poly=np.asarray(data["outer"])
    candidates=data["candidates"]
    if len(poly)==0 or not candidates:
        ax.text(.5,.5,"没有可用候选区域",ha="center",transform=ax.transAxes)
    else:
        points=np.asarray([r["point"] for r in candidates])
        low=np.minimum(poly.min(axis=0),points.min(axis=0))-120
        high=np.maximum(poly.max(axis=0),points.max(axis=0))+120
        x=np.linspace(low[0],high[0],240)
        y=np.linspace(low[1],high[1],240)
        xx,yy=np.meshgrid(x,y)
        max_distance=np.zeros_like(xx)
        for v in poly:
            max_distance=np.maximum(max_distance,np.hypot(xx-v[0],yy-v[1]))
        ax.contourf(xx,yy,max_distance,levels=[0,1000],colors=["#E5EFE6"],alpha=.8)
        ax.contour(xx,yy,max_distance,levels=[1000],colors=["#46856A"],linewidths=.8)
        ax.add_patch(Polygon(poly,facecolor="#CCE1EB",edgecolor="#477C99",label="首次可行外包络"))
        for safe,marker,label in [(True,"o","安全候选"),(False,"x","风险候选")]:
            group=[r for r in candidates if r["distance_safe"]==safe]
            if group:
                p=np.asarray([r["point"] for r in group])
                scatter=ax.scatter(p[:,0],p[:,1],c=[r["min_gamma"] for r in group],
                                   cmap="viridis",vmin=0,vmax=1,marker=marker,s=30,label=label)
        fig.colorbar(scatter,ax=ax,label="最小场景交会质量")
        ax.scatter(*data["selected"],marker="*",s=150,color="#B46A70",label="选中点",zorder=5)
        ax.scatter(*data["observation"]["position"],marker="s",s=30,color="black",label="首次检测点")
        ax.legend(loc="upper center",bbox_to_anchor=(.5,-.15),ncol=3)
    geometry_axes(ax)
    ax.set_title("第二检测点：浅绿区域满足保守接收条件（"+source_label(data)+"）")
    save(fig,output,data["source"],"先区分保证接收区域，再权衡交会质量与移动成本")

if __name__=="__main__":
    cli(plot,"outputs/problem2.json","outputs/figures/fig03_candidate_region")
