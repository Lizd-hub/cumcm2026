"""轨迹共享渲染器；坐标均来自已接受动作，不绘制未知真值。"""
from matplotlib.collections import LineCollection
from matplotlib.patches import Circle
from figures.style import setup,geometry_axes,save,COLORS,source_label

def draw_trajectory(data,output,problem):
    if data["problem"]!=problem:
        raise ValueError("wrong problem result")
    fig,ax=setup()
    names=dict(coverage="覆盖移动",localization="定位移动",clear="清除移动",fallback="光学兜底")
    for phase in names:
        segments=[]
        for e in data["events"]:
            if e.get("kind")=="action" and e["path"] in ("/measure","/clear") and e["phase"]==phase:
                segments.append([e["before"]["position"],e["after"]["position"]])
        if segments:
            ax.add_collection(LineCollection(segments,colors=COLORS[phase],linewidths=.65,alpha=.8,label=names[phase]))
    success=[e["after"]["position"] for e in data["events"] if e.get("kind")=="action"
             and e.get("response",{}).get("clear_result")=="success"]
    if success:
        ax.scatter(*zip(*success),s=25,marker="*",color="#46856A",zorder=5,label="成功清除位置")
    ax.add_patch(Circle((0,0),1800,fill=False,color="#777777",lw=.8))
    ax.scatter(0,0,color="black",marker="s",s=25,label="起点")
    ax.autoscale_view()
    geometry_axes(ax)
    status="完整证书已建立" if data["complete"] else "未完成"
    ax.set_title(f"问题{problem}完整动作轨迹 · {source_label(data)} · {status}")
    ax.legend(loc="upper center",bbox_to_anchor=(.5,-.15),ncol=3)
    save(fig,output,data["source"],"展示覆盖、定位与清除的实际移动路径及终止证书状态")
