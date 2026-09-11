"""汇总离线实验和题面正式测试表；缺失记录保持空白。"""
import argparse
import csv
from pathlib import Path
from legacy_solution.common.logging_io import read_json,write_json

def write_csv(path,rows,fields):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

def summarize(summary_path,output,formal_records=None):
    output=Path(output)
    rows=read_json(summary_path)
    write_csv(output/"trial_summary.csv",rows,list(rows[0]) if rows else ["problem","seed"])
    pairs=[]
    for p in (3,4):
        for seed in sorted({r["seed"] for r in rows if r["problem"]==p}):
            by={r["strategy"]:r for r in rows if r["problem"]==p and r["seed"]==seed}
            if "active" in by and "baseline" in by:
                a,b=by["active"],by["baseline"]
                pairs.append(dict(problem=p,seed=seed,both_complete=a["complete"] and b["complete"],
                                  baseline_time_s=b["virtual_time_s"],active_time_s=a["virtual_time_s"],
                                  saved_time_s=b["virtual_time_s"]-a["virtual_time_s"]))
    write_csv(output/"paired_comparison.csv",pairs,["problem","seed","both_complete","baseline_time_s","active_time_s","saved_time_s"])
    records=read_json(formal_records) if formal_records else []
    for p in (3,4):
        selected=[r for r in records if r.get("problem")==p]
        if len(selected)>3 or any(r.get("source")!="official_formal" for r in selected):
            raise ValueError("formal table requires at most three official_formal records per problem")
        table=[]
        for i in range(3):
            r=selected[i] if i<len(selected) else {}
            count=r.get("cleared_count")
            table.append({"测试序号":i+1,"测试案例编码":r.get("case_code",""),
                          "清除干扰源个数":count,"平均定位清除时间":r.get("virtual_time_s",0)/count if count else None,
                          "程序运行时间":r.get("real_time_s"),"状态":"已提供" if r else "缺少官方测试记录",
                          "日志原文件名":r.get("log_filename","")})
        write_csv(output/f"problem{p}_formal.csv",table,list(table[0]))
    write_json(output/"paired_comparison.json",pairs)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",default="outputs/benchmark/summary.json")
    p.add_argument("--output",default="outputs/tables")
    p.add_argument("--formal-records")
    a=p.parse_args()
    summarize(a.input,a.output,a.formal_records)

if __name__=="__main__":
    main()
