import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import sqlite_vec
import worker


class LibraryQuestionTest(unittest.TestCase):
    def test_answers_general_question_with_no_documents_or_citations(self):
        request = {"question": "什么是向量数据库？", "documents": [], "allowGeneral": True}
        with patch.object(worker, "retrieve") as retrieve, patch.object(worker, "ollama", return_value={
            "message": {"content": '{"route":"general","answer":"用于存储和检索向量的数据库。"}'},
        }) as chat:
            response = worker.ask(request)
        retrieve.assert_not_called()
        self.assertEqual(chat.call_args.kwargs["messages"][-1]["content"], request["question"])
        self.assertEqual(response["workflow"]["route"], "general")
        self.assertEqual(response["sources"], [])

    def test_keeps_scoped_questions_and_cited_answers_grounded(self):
        source = {"text": "请于 17:30 前归还。"}
        request = {"question": "最迟几点归还？", "documents": [{"documentId": "test"}]}
        with patch.object(worker, "retrieve", return_value=[source]), patch.object(worker, "generate_answer") as grounded, \
                patch.object(worker, "generate_general_answer") as general:
            grounded.return_value = worker.EMPTY
            self.assertEqual(worker.ask(request)["workflow"]["route"], "unverified")
            grounded.return_value = {"answer": "17:30", "sources": [source]}
            self.assertEqual(worker.ask(dict(request, allowGeneral=True))["sources"], [source])
            general.assert_not_called()

    def test_explicit_document_question_does_not_fall_back_to_general_knowledge(self):
        request = {"question": "根据这份资料，实训几点开始？", "documents": [], "allowGeneral": True}
        with patch.object(worker, "ollama") as chat:
            self.assertEqual(worker.ask(request)["workflow"]["route"], "no_match")
        chat.assert_not_called()

    def test_general_fallback_reuses_the_document_model_context(self):
        request = {"question": "什么是向量数据库？", "documents": [{}], "allowGeneral": True}
        replies = [
            {"message": {"content": '{"answer":"","quotes":[]}'}},
            {"message": {"content": '{"route":"general","answer":"用于存储和检索向量的数据库。"}'}},
        ]
        with patch.object(worker, "retrieve", return_value=[{"text": "借用器材须登记。"}]), \
                patch.object(worker, "ollama", side_effect=replies) as chat:
            response = worker.ask(request)
        self.assertEqual(response["workflow"]["route"], "general")
        self.assertEqual([call.kwargs["options"]["num_ctx"] for call in chat.call_args_list], [4096, 4096])


class ModelMigrationTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "old.sqlite3"
        with closing(worker.vector_db(self.path)) as db, db:
            db.execute("CREATE TABLE passages (id INTEGER PRIMARY KEY, page INTEGER, text TEXT NOT NULL)")
            db.execute("INSERT INTO passages VALUES(1,2,'LAB-07 存放于 A 柜')")
            db.execute("CREATE VIRTUAL TABLE chunks USING vec0(v float[1024] distance_metric=cosine, chunk_size=32)")
            db.execute("INSERT INTO chunks(rowid,v) VALUES(1,?)", (sqlite_vec.serialize_float32([1] * 1024),))

    def test_migrates_old_index_once_and_keeps_passages(self):
        sample = sqlite_vec.serialize_float32([1] * worker.DIMENSION)
        with patch.object(worker, "embeddings", return_value=[sample]) as embeddings:
            worker.ensure_current_vectors(self.path)
            worker.ensure_current_vectors(self.path)
        embeddings.assert_called_once_with(["LAB-07 存放于 A 柜"])
        with closing(worker.vector_db(self.path, "ro")) as db:
            self.assertIsNotNone(worker.has_current_vectors(db))
            self.assertEqual(db.execute(f"SELECT rowid FROM {worker.VECTOR_TABLE}").fetchall(), [(1,)])
            self.assertEqual(db.execute("SELECT page FROM passages").fetchone(), (2,))

    def test_model_failure_leaves_previous_index_readable(self):
        with patch.object(worker, "embeddings", side_effect=ValueError("test service failure")):
            with self.assertRaises(ValueError):
                worker.ensure_current_vectors(self.path)
        with closing(worker.vector_db(self.path, "ro")) as db:
            self.assertIsNone(worker.has_current_vectors(db))
            self.assertEqual(db.execute("SELECT rowid FROM chunks").fetchall(), [(1,)])
