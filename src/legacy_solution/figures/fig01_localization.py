"""角域交、最远点对与最小包围圆，局部放大显示几何细节。"""
import numpy as np
from matplotlib.patches import Circle,Polygon
from legacy_solution.figures.style import setup,geometry_axes,save,cli,source_label

def plot(data,output="outputs/figures/fig01_localization"):
    fig,ax=setup()
    if data["status"]!="bounded":
        ax.text(.5,.5,"定位区域："+data["status"],ha="center",transform=ax.transAxes)
    else:
        vertices=np.asarray(data["vertices"])
        ax.add_patch(Polygon(vertices,facecolor="#CCE1EB",edgecolor="#477C99",label="定位区域"))
        pair=np.asarray(data["farthest_pair"])
        ax.plot(pair[:,0],pair[:,1],color="#B46A70",lw=2,label="最远点对")
        ax.add_patch(Circle(data["center"],data["radius"],fill=False,color="#46856A",ls="--",label="最小包围圆"))
        for o in data["observations"]:
            s=np.array(o["position"])
            length=max(np.linalg.norm(vertices-s,axis=1))*1.3
            for error in [-data["delta_deg"],0,data["delta_deg"]]:
                angle=np.deg2rad(o["bearing_deg"]+error)
                q=s+length*np.array([np.cos(angle),np.sin(angle)])
                ax.plot([s[0],q[0]],[s[1],q[1]],color="#9CA4AA",ls="--" if error else "-",lw=.7,zorder=0)
        center=np.array(data["center"])
        span=max(data["radius"]*1.65,1.0)
        ax.set_xlim(center[0]-span,center[0]+span)
        ax.set_ylim(center[1]-span,center[1]+span)
        ax.legend(loc="upper center",bbox_to_anchor=(.5,-.15),ncol=3)
    geometry_axes(ax)
    ax.set_title("测向角域交：局部放大（"+source_label(data)+"）")
    save(fig,output,data["source"],"定位区域直径在凸包顶点对上取得")

if __name__=="__main__":
    cli(plot,"outputs/problem1.json","outputs/figures/fig01_localization")
