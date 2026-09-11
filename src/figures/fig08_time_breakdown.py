"""实际运行的五类虚拟耗时分解。"""
from figures.style import setup,save,cli,source_label

def plot(data,output="outputs/figures/fig08_time_breakdown"):
    fig,ax=setup()
    keys=["movement","measurement","switching","clear_success","clear_failure"]
    labels=["移动","测向","频道切换","成功清除","失败清除"]
    values=[data["time_breakdown"][k] for k in keys]
    bars=ax.barh(labels,values,color=["#477C99","#90B5C5","#B6BFCC","#46856A","#B46A70"])
    ax.bar_label(bars,fmt="%.1f",padding=5)
    ax.set_xlim(0,max(values,default=1)*1.22+1)
    ax.set_xlabel("虚拟耗时 / 秒")
    ax.set_title(f"问题{data['problem']}时间分解 · {source_label(data)}")
    save(fig,output,data["source"],"区分移动、检测、切换、成功和失败清除的时间成本")

if __name__=="__main__":
    cli(plot,"outputs/problem4.json","outputs/figures/fig08_time_breakdown")
