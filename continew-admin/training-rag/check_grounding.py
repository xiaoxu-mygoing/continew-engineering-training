"""Small live acceptance check. Uses the actual local models and a disposable private index."""
import base64
import os
import tempfile
import uuid
from pathlib import Path

from worker import ask, build


def main():
    project = Path(__file__).resolve().parents[2]
    fixture = (project / "任务2演示资料" / "工程实训器材借用指南.txt").read_bytes()
    with tempfile.TemporaryDirectory(dir=str(project / "local-runtime" / "rag")) as tmp:
        os.environ["TRAINING_RAG_HOME"] = tmp
        req = dict(documentId=str(uuid.uuid4()), version=1,
                   file=base64.b64encode(fixture).decode())
        doc = dict(documentId=req["documentId"], version=1, fileName="借用指南.txt")
        build(dict(doc, file=req["file"]))
        for question, expected in [
            ("普通借用最迟几点归还？", "17:30"),
            ("LAB-12 泡棉标尺存放在哪个柜子？", "C 柜"),
            ("一台 LAB-07 便携示波器的采购价格是多少元？", None),
            ("学校食堂今天的午餐套餐多少钱？", None),
        ]:
            result = ask({"documents":[doc], "question":question})
            flow = result["workflow"]
            assert flow["documents"] == 1 and flow["citations"] == len(result["sources"])
            if expected is not None:
                assert flow["route"] == "answered"
            elif "午餐" in question:
                assert flow["route"] == "no_match" and flow["candidates"] == 0
            else:
                assert flow["route"] == "unverified" and flow["candidates"] > 0
            print(question, result["answer"], flush=True)
            if expected is None:
                assert not result["sources"] and "未找到依据" in result["answer"]
            else:
                assert result["sources"] and expected in result["sources"][0]["text"]
                assert expected.replace(" ", "") in result["answer"].replace(" ", "").replace("：", ":")


if __name__ == "__main__":
    main()
