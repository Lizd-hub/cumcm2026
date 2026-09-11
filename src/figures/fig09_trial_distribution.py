"""同场景配对比较，保留失败案例标记。"""
import numpy as np
from figures.style import setup,save,cli

def plot(data,output="outputs/figures/fig09_trial_distribution"):
    fig,ax=setup()
    if any(r.get("source")!="offline" for r in data):
        raise ValueError("此图仅接受离线配对实验")
    for problem,base in [(3,0),(4,3)]:
        seeds=sorted({r["seed"] for r in data if r["problem"]==problem})
        for i,seed in enumerate(seeds):
            rows={r["strategy"]:r for r in data if r["problem"]==problem and r["seed"]==seed}
            if not all(k in rows for k in ["baseline","active"]):
                continue
            jitter=(i-(len(seeds)-1)/2)*min(.015,.3/max(1,len(seeds)))
            vals=[rows[k]["virtual_time_s"] for k in ["baseline","active"]]
            ax.plot([base+jitter,base+1+jitter],vals,color="#BBC2C7",lw=.7,zorder=1)
            for x,k,v in zip([base+jitter,base+1+jitter],["baseline","active"],vals):
                ax.scatter(x,v,s=22,marker="o" if rows[k]["complete"] else "x",
                           color="#477C99" if k=="baseline" else "#D49348",zorder=2)
        ax.text(base+.5,1.01,f"问题{problem}：n={len(seeds)}",ha="center",transform=ax.get_xaxis_transform())
    ax.set_xticks([0,1,3,4],["基线","主动定位","基线","主动定位"])
    ax.set_ylabel("虚拟总耗时 / 秒")
    ax.set_xlim(-.5,4.5)
    ax.set_title("离线配对实验：连线对应相同场景，叉号表示未完成",pad=28)
    save(fig,output,"offline","同种子配对比较耗时，同时显示不完整运行")

if __name__=="__main__":
    cli(plot,"outputs/benchmark/summary.json","outputs/figures/fig09_trial_distribution")
