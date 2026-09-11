import json
from pathlib import Path
import pytest
from experiments.summarize import summarize
from common.logging_io import write_json

def test_formal_missing_is_not_filled_with_offline(tmp_path):
    summary=tmp_path/"summary.json"
    write_json(summary,[dict(problem=3,seed=1,strategy="active",source="offline",complete=True,
                             virtual_time_s=999,cleared_count=10)])
    summarize(summary,tmp_path/"tables")
    text=(tmp_path/"tables/problem3_formal.csv").read_text(encoding="utf-8-sig")
    assert "缺少官方测试记录" in text
    assert "999" not in text

def test_offline_record_cannot_be_formal(tmp_path):
    summary=tmp_path/"summary.json"
    write_json(summary,[])
    formal=tmp_path/"formal.json"
    write_json(formal,[dict(problem=3,source="offline")])
    with pytest.raises(ValueError):
        summarize(summary,tmp_path/"tables",formal)
