"""Deterministic regression tests; model calls and Neo4j are tested separately."""
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
    def test_local_edge_ids_do_not_hide_other_documents(self):
        result = worker.subgraph([graph("first", "A柜"), graph("second", "B柜")], "LAB-07在哪里")
        self.assertEqual({item["documentId"] for item in result[3]}, {"first", "second"})

    def test_model_rejection_stays_unverified(self):
        with patch.object(worker, "load", return_value=graph("first", "A柜")), \
                patch.object(worker, "answer_with_model", return_value=None):
            result = worker.ask({"documents": [{}], "question": "LAB-07多少钱"})
        self.assertEqual(result["workflow"]["route"], "unverified")
        self.assertEqual(result["sources"], [])

    def test_no_entity_does_not_call_model(self):
        with patch.object(worker, "load", return_value=graph("first", "A柜")), \
                patch.object(worker, "answer_with_model") as model:
            result = worker.ask({"documents": [{}], "question": "另一个设备在哪里"})
        model.assert_not_called()
        self.assertEqual(result["workflow"]["route"], "no_match")


if __name__ == "__main__":
    unittest.main()
