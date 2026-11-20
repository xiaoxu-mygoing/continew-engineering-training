"""Deterministic regression tests; model calls and Neo4j are tested separately."""
import json
import unittest
from unittest.mock import patch

import worker


def graph(doc_id, text):
    return {
        "doc": {"documentId": doc_id, "version": 1, "fileName": "sample.txt"},
        "names": {1: {"name": "LAB-07", "kind": "设备"}, 2: {"name": text, "kind": "地点"}},
        "edges": [{"id": 1, "source": 1, "target": 2, "predicate": "存放",
                   "chunk": 1, "page": None, "evidence": text}],
    }


class GraphRegressionTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(worker, "embeddings", return_value=[[0.0] * 1024])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_local_edge_ids_do_not_hide_other_documents(self):
        result = worker.subgraph([graph("first", "A柜"), graph("second", "B柜")], "LAB-07在哪里")
        self.assertEqual({item["documentId"] for item in result[3]}, {"first", "second"})

    def test_model_rejection_stays_unverified(self):
        with patch.object(worker, "load", return_value=graph("first", "A柜")), \
                patch.object(worker, "answer_with_model", return_value=None):
            result = worker.ask({"documents": [{}], "question": "LAB-07多少钱"})
        self.assertEqual(result["workflow"]["route"], "unverified")
        self.assertEqual(result["sources"], [])

    def test_semantic_seed_without_literal_name(self):
        data = graph("first", "A柜")
        data["semantic_seeds"] = {1}
        self.assertEqual(len(worker.subgraph([data], "测量仪器在哪")[1]), 1)

    def test_different_device_code_does_not_use_semantic_seed(self):
        data = graph("first", "A柜")
        data["semantic_seeds"] = {1}
        self.assertEqual(worker.subgraph([data], "OTHER-99在哪")[1], [])

    def test_code_in_evidence_matches_when_entity_name_omits_it(self):
        data = graph("first", "设备 LAB-07 存放在A柜。")
        data["names"][1]["name"] = "测量仪器"
        self.assertEqual(len(worker.subgraph([data], "LAB-07在哪")[1]), 1)
        self.assertEqual(worker.subgraph([data], "LAB-070在哪")[1], [])

    def test_sentence_chunks_preserve_all_facts(self):
        text = "仪器存放在A柜。仪器由王老师管理。\n归还时间为17:00。"
        rows = worker.passages(text.encode(), "sample.txt")
        self.assertEqual([r[2] for r in rows], ["仪器存放在A柜。", "仪器由王老师管理。", "归还时间为17:00。"])

    def test_verbal_abstention_is_not_a_verified_answer(self):
        reply = {"answer": "没有明确答案", "quotes": ["仪器存放在A柜"]}
        with patch.object(worker, "ollama", return_value={"message": {"content": json.dumps(reply)}}):
            self.assertIsNone(worker.answer_with_model([{"text": "仪器存放在A柜"}], "仪器多少钱"))

    def test_no_entity_does_not_call_model(self):
        with patch.object(worker, "load", return_value=graph("first", "A柜")), \
                patch.object(worker, "answer_with_model") as model:
            result = worker.ask({"documents": [{}], "question": "另一个设备在哪里"})
        model.assert_not_called()
        self.assertEqual(result["workflow"]["route"], "no_match")


if __name__ == "__main__":
    unittest.main()
