"""Representative fake inputs -> replies and stored JSON, in a temporary data directory (no network)."""
import json
import sys
import pathlib
import unittest
OUT = pathlib.Path(__file__).with_suffix(".json")

sys.path.insert(0, "scripts")
sys.path.insert(0, "tests")
sys.stdout.reconfigure(encoding="utf-8")
import common as c  # noqa: E402
import candidate_feedback as fb  # noqa: E402
import telegram_cmd  # noqa: E402
from test_v1_feedback import ReplyFixture  # noqa: E402


class Evidence(ReplyFixture):
    def runTest(self):
        cases = [("관심없음", 501), ("자세히", 501), ("추적", 501), ("추적", 502), ("보류", 168), ("이 회사 좋네", 501)]
        out = []
        for i, (word, to) in enumerate(cases, 1):
            self.sent.clear()
            self.run_updates(self.reply(i, word, to=to))
            out.append({"input": {"update_id": i, "text": word, "reply_to_message_id": to},
                        "replies": [m if len(m) < 300 else m[:300] + " …(이하 생략)" for m in self.sent]})
        OUT.write_text(json.dumps({"cases": out,
                          "command_queue.json": c.read_json(c.DATA_DIR / "command_queue.json", {}),
                          "candidate_feedback.json": fb.load(),
                          "summary": fb.summary()}, ensure_ascii=False, indent=1), encoding="utf-8")


unittest.TextTestRunner(stream=open("NUL", "w") if sys.platform == "win32" else None).run(Evidence())
