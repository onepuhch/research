"""J3 tool: a fake loopback Ollama only (no install, no download, no real inference)."""
import gzip
import hashlib
import json
import pathlib
import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))
import candidate_context as ctx  # noqa: E402
import common as c  # noqa: E402
import company_filings as cf  # noqa: E402
import local_context_benchmark as lb  # noqa: E402
from test_candidate_context import claim, release_record  # noqa: E402

LABELS = {"companies": {"AAA": {
    "facts": [{"id": "aaa_rev", "metric_terms": ["revenue"], "figures": ["$120.0 million", "40%"], "block": "p2",
               "important": True}],
    "critical": [{"id": "aaa_wrong", "metric_terms": ["net income"], "figures": ["$120.0 million"]}],
    "counter": [{"id": "aaa_tax", "anchors": ["one-time tax benefit"], "block": "p4"}]}}}


class FakeOllama(BaseHTTPRequestHandler):
    mode = "ok"
    digest = "sha256:aaa"
    answer = None
    chats = 0
    unloads = 0

    def log_message(self, *args):
        pass

    def send(self, status, body):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/version":
            return self.send(200, {"version": "0.0-test"})
        if self.path == "/api/tags":
            return self.send(200, {"models": [{"name": "m:1", "model": "m:1", "digest": type(self).digest,
                                               "size": 1, "details": {"quantization_level": "Q4_K_M"}}]})
        self.send(404, {})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        cls = type(self)
        if self.path == "/api/generate" and body.get("keep_alive") == 0:
            cls.unloads += 1
            return self.send(200, {"done": True})
        cls.chats += 1
        mode = cls.mode
        if mode == "timeout":
            time.sleep(1.5)
        if mode == "oom":
            return self.send(500, {"error": "cudaMalloc failed: out of memory"})
        if mode == "busy":
            return self.send(503, {"error": "server busy"})
        if mode == "api_garbage":
            return self.send(200, b"not json")
        content = json.dumps(cls.answer) if mode in ("ok", "timeout") else (
            '{"claims": [' if mode == "truncated" else "no json here")
        reply = {"message": {"role": "assistant", "content": content}, "done": True,
                 "done_reason": "length" if mode == "truncated" else "stop", "total_duration": 5,
                 "load_duration": 1, "prompt_eval_count": 100, "eval_count": 50, "eval_duration": 3}
        self.send(200, reply)


class QuietServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass  # the client gave up first (timeout test)


class BenchmarkTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        # A fixed source copy with one stored release.
        data = self.tmp / "data"
        with mock.patch.object(c, "DATA_DIR", data):
            cf.store_document(release_record())
        self.source = self.tmp / "source"
        shutil.copytree(data / "company_documents", self.source / "company_documents")
        path = self.source / "company_documents" / "DOC-A.json.gz"
        with gzip.open(path, "rt", encoding="utf-8") as h:
            doc = json.load(h)
        self.manifest = self.tmp / "manifest.json"
        self.manifest.write_text(json.dumps({
            "documents": [{"ticker": "AAA", "candidate_id": "CAN-1", "document_id": "DOC-A",
                           "raw_sha256": doc["raw_sha256"],
                           "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                           "blocks_sha256": lb.sha256(lb.canonical(doc["blocks"])),
                           "eps_target_period": "2027-12-31", "issuer_name": "AAA Corp"}],
            "cases": [{"case_id": "AAA-A", "group": "A", "split": "dev", "ticker": "AAA", "document_id": "DOC-A",
                       "blocks": "relevant_blocks"},
                      {"case_id": "AAA-B", "group": "B", "split": "eval", "ticker": "AAA", "document_id": "DOC-A",
                       "blocks": ["p2"]}],
            "stability_cases": ["AAA-B"], "limits": {"max_requests": 26, "total_inference_s": 2700}}))
        self.out = self.tmp / "experiment"
        # A fake local server on a free loopback port.
        FakeOllama.mode, FakeOllama.digest, FakeOllama.chats, FakeOllama.unloads = "ok", "sha256:aaa", 0, 0
        FakeOllama.answer = {"claims": [claim(), claim(metric="net income", figures=["$120.0 million"])],
                             "limitations": [], "next_check": [], "link": "unconfirmed"}
        self.server = QuietServer(("127.0.0.1", 0), FakeOllama)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.endpoint = f"http://127.0.0.1:{self.server.server_address[1]}"
        # The pipeline's writers must never run; its data directory must stay untouched.
        self.pipeline_data = self.tmp / "pipeline_data"
        self.pipeline_data.mkdir()
        for patch in (mock.patch.object(c, "DATA_DIR", self.pipeline_data),
                      mock.patch.object(ctx, "run_sources", side_effect=AssertionError("run_sources")),
                      mock.patch.object(ctx, "run_drafts", side_effect=AssertionError("run_drafts")),
                      mock.patch.object(ctx, "store_context", side_effect=AssertionError("store_context")),
                      mock.patch.object(c, "load_dotenv_value", side_effect=AssertionError(".env")),
                      mock.patch.object(lb, "gpu_memory_mib", return_value=None)):
            patch.start()
            self.addCleanup(patch.stop)

    def prepared(self):
        return lb.prepare(self.source, self.manifest, self.out)

    def run_bench(self, **kw):
        kw.setdefault("label", "final")
        return lb.run(self.out, "m:1", self.endpoint, kw.pop("label"), kw.pop("cases", None),
                      kw.pop("resume", True), **kw)

    def result(self, case="AAA-B", label="final"):
        return json.loads((self.out / "runs" / label / f"{case}.json").read_text(encoding="utf-8"))

    def test_prepare_and_report_make_no_network_request(self):
        with mock.patch.object(socket, "socket", side_effect=AssertionError("network")):
            self.prepared()
        self.run_bench()
        with mock.patch.object(socket, "socket", side_effect=AssertionError("network")):
            out = lb.report(self.out, self.write_labels(), self.out / "report")
        self.assertEqual(out["summary"]["all"]["ran"], 2)
        self.assertEqual(list(self.pipeline_data.iterdir()), [])  # no pipeline file written

    def write_labels(self):
        path = self.tmp / "labels.json"
        path.write_text(json.dumps(LABELS))
        return path

    def test_normal_answer_keeps_raw_text_stats_and_v4_validation(self):
        self.prepared()
        summary = self.run_bench()
        self.assertEqual((summary["ran"], summary["failed"]), (2, 0))
        res = self.result()
        self.assertIsNone(res["failure"])
        self.assertEqual(json.loads(res["raw_content"]), FakeOllama.answer)
        self.assertEqual(res["stats"]["prompt_eval_count"], 100)
        self.assertEqual(res["parser_version"], ctx.PARSER_VERSION)
        self.assertEqual(len(res["validation"]["claims"]), 1)  # 'net income' with the revenue figure is refused
        scored = lb.report(self.out, self.write_labels(), self.out / "report")["summary"]["all"]
        self.assertEqual((scored["accepted"], scored["correct"], scored["critical_accepted"]), (2, 2, 0))
        self.assertGreaterEqual(scored["critical_emitted_rejected"], 1)

    def test_failures_are_results_and_never_repaired(self):
        self.prepared()
        for mode, kind in (("garbage", "bad_json"), ("truncated", "truncated"), ("busy", "busy"),
                           ("api_garbage", "bad_api_json")):
            FakeOllama.mode = mode
            self.run_bench(label=mode, cases=["AAA-B"])
            self.assertEqual(self.result(label=mode)["failure"], kind, mode)
            self.assertNotIn("validation", self.result(label=mode))

    def test_oom_and_timeout_unload_the_model(self):
        self.prepared()
        FakeOllama.mode = "oom"
        self.run_bench(label="oom", cases=["AAA-B"])
        self.assertEqual(self.result(label="oom")["failure"], "oom")
        FakeOllama.mode = "timeout"
        self.run_bench(label="slow", cases=["AAA-B"], timeout=0.3)
        self.assertEqual(self.result(label="slow")["failure"], "timeout")
        self.assertEqual(FakeOllama.unloads, 2)

    def test_connection_refused(self):
        self.prepared()
        free = socket.socket()
        free.bind(("127.0.0.1", 0))
        port = free.getsockname()[1]
        free.close()
        case = json.loads((self.out / "cases" / "AAA-B.json").read_text(encoding="utf-8"))
        res = lb.run_case(lb.Loopback(f"http://127.0.0.1:{port}"), case, "m:1", lb.OPTIONS, {}, 15)  # Windows retries ~2s
        self.assertEqual(res["failure"], "connection_refused")

    def test_remote_endpoints_are_refused(self):
        for endpoint in ("http://example.com:11434", "https://127.0.0.1:11434", "http://10.0.0.5:11434",
                         "http://127.0.0.1:11434/proxy"):
            with self.assertRaises(ValueError):
                lb.Loopback(endpoint)

    def test_resume_skips_only_identical_inputs(self):
        self.prepared()
        self.run_bench()
        self.assertEqual(self.run_bench()["skipped"], 2)
        self.assertEqual(self.run_bench(options={"num_ctx": 8192})["ran"], 2)  # settings changed
        FakeOllama.digest = "sha256:bbb"
        self.assertEqual(self.run_bench(options={"num_ctx": 8192})["ran"], 2)  # model changed
        path = self.out / "cases" / "AAA-B.json"
        case = json.loads(path.read_text(encoding="utf-8"))
        case["input_sha256"] = "changed"
        path.write_text(json.dumps(case), encoding="utf-8")
        self.assertEqual(self.run_bench(options={"num_ctx": 8192})["ran"], 1)  # only the changed input
        with mock.patch.object(ctx, "PARSER_VERSION", "context-check-v9"):
            self.assertEqual(self.run_bench(options={"num_ctx": 8192})["ran"], 2)  # validator changed

    def test_request_cap_stops_the_run(self):
        self.prepared()
        summary = self.run_bench(max_requests=1)
        self.assertEqual((summary["ran"], summary["stopped"]), (1, "max_requests"))

    def test_changed_source_is_dataset_missing_not_refetched(self):
        path = self.source / "company_documents" / "DOC-A.json.gz"
        path.write_bytes(path.read_bytes() + b"x")
        self.prepared()
        meta = json.loads((self.out / "experiment.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["dataset_missing"], {"DOC-A": "file_hash_mismatch"})
        self.assertEqual({x["status"] for x in meta["cases"]}, {"dataset_missing"})
        self.assertEqual(self.run_bench()["ran"], 0)
        self.assertEqual(FakeOllama.chats, 0)

    def test_output_never_goes_to_pipeline_data_or_code(self):
        for bad in (lb.ROOT / "data" / "processed" / "x", lb.ROOT / "config", lb.ROOT / "scripts" / "x"):
            with self.assertRaises(ValueError):
                lb.prepare(self.source, self.manifest, bad)

    def test_kept_answers_are_revalidated_offline(self):
        self.prepared()
        self.run_bench()
        res = self.result()
        case = json.loads((self.out / "cases" / "AAA-B.json").read_text(encoding="utf-8"))
        again = ctx.validate_draft(json.loads(res["raw_content"]), case["blocks"], case["issuer"])
        self.assertEqual(again, res["validation"])

    def test_stability_compares_the_same_case(self):
        self.prepared()
        self.run_bench()
        self.run_bench(label="stability", cases=["AAA-B"])
        out = lb.report(self.out, self.write_labels(), self.out / "report")
        self.assertEqual(out["stability"], [{"case_id": "AAA-B", "same_content": True, "critical_accepted": [],
                                             "failure": None}])


if __name__ == "__main__":
    unittest.main()
