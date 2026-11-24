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
        patcher = patch.object(worker, "embeddings", return_value=[[0.0] * worker.DIMENSION])
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

    def test_only_cited_passages_are_returned_once_across_documents(self):
        graphs = [graph("first", "LAB-07 存放在 A 柜。"),
                  graph("unquoted", "LAB-07 的配件放在 B 柜。"),
                  graph("last", "LAB-07 由张老师管理。")]
        reply = {"answer": "LAB-07 存放在 A 柜，由张老师管理。",
                 "quotes": ["由张老师管理", "存放在 A 柜", "LAB-07 存放在 A 柜。"]}
        with patch.object(worker, "load", side_effect=graphs), \
                patch.object(worker, "ollama", return_value={"message": {"content": json.dumps(reply)}}):
            result = worker.ask({"documents": [{}, {}, {}], "question": "LAB-07 在哪，由谁管理？"})
        self.assertEqual(result["workflow"]["route"], "answered")
        self.assertEqual([item["documentId"] for item in result["sources"]], ["last", "first"])
        self.assertEqual(result["sources"][0]["text"], "LAB-07 由张老师管理。")
        self.assertEqual(len(result["edges"]), 3)

    def test_numbers_from_uncited_passages_do_not_validate_answer(self):
        evidence = [{"text": "设备存放在 A 柜。"}, {"text": "归还时间是 17:30。"}]
        reply = {"answer": "设备在 A 柜，归还时间是 17:30。", "quotes": ["设备存放在 A 柜。"]}
        with patch.object(worker, "ollama", return_value={"message": {"content": json.dumps(reply)}}):
            self.assertIsNone(worker.answer_with_model(evidence, "设备在哪，几点归还？"))

    def test_unmatched_quote_does_not_validate_answer(self):
        evidence = [{"text": "设备存放在 A 柜。"}]
        reply = {"answer": "设备在 A 柜。", "quotes": ["存放在 A 柜", "柜子在实验室"]}
        with patch.object(worker, "ollama", return_value={"message": {"content": json.dumps(reply)}}):
            self.assertIsNone(worker.answer_with_model(evidence, "设备在哪？"))

    def test_neighboring_relation_alone_does_not_prove_device_location(self):
        evidence = [{"text": "LAB-07 设备在 A 柜。"}, {"text": "A 柜位于教学仓库。"}]
        reply = {"answer": "A 柜。", "quotes": ["A 柜位于教学仓库。"]}
        with patch.object(worker, "ollama", return_value={"message": {"content": json.dumps(reply)}}):
            self.assertIsNone(worker.answer_with_model(evidence, "LAB-07 设备在哪？"))

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
