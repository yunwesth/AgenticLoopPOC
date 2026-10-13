import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from loop import clean, run_agent  # noqa: E402
from trace import TRACE_END, TRACE_HEAD, format_event, strip_trace  # noqa: E402
from tools import calculator, run_tool  # noqa: E402


class CalculatorTests(unittest.TestCase):
    def test_precedence(self):
        self.assertEqual(calculator("2+3*4"), "14")
        self.assertEqual(calculator("17*23+4"), "395")

    def test_pow_div_parens(self):
        self.assertEqual(calculator("2**10"), "1024")
        self.assertEqual(calculator("(1+2)/4"), "0.75")
        self.assertEqual(calculator("-3 + 5"), "2")

    def test_rejects_unsafe(self):
        for bad in ("__import__('os').system('id')", "abs(1)", "a+1", "'x'*3", "(1).real", "1 if 1 else 2"):
            self.assertTrue(calculator(bad).startswith("error"), bad)

    def test_errors_are_text(self):
        self.assertEqual(calculator("1/0"), "error: division by zero")
        self.assertIn("exponent", calculator("2**99999"))
        self.assertIn("longer", calculator("1+" * 150 + "1"))
        self.assertTrue(calculator("").startswith("error"))

    def test_unknown_tool_and_bad_args(self):
        self.assertIn("unknown tool", run_tool("shell", {}))
        self.assertIn("bad arguments", run_tool("calculator", {"wrong": 1}))


def call(expr):
    return {"role": "assistant", "content": "",
            "tool_calls": [{"function": {"name": "calculator", "arguments": {"expression": expr}}}]}


class LoopTests(unittest.TestCase):
    def test_one_tool_call_then_answer(self):
        seen = []
        script = [call("17*23+4"), {"role": "assistant", "content": "It is 395."}]

        def chat(messages, tools):
            seen.append(list(messages))
            return script[len(seen) - 1]

        out = run_agent([{"role": "user", "content": "17*23+4?"}], chat)
        self.assertEqual(out, "It is 395.")
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[1][-1], {"role": "tool", "tool_name": "calculator", "content": "395"})

    def test_step_cap(self):
        n = []
        out = run_agent([{"role": "user", "content": "x"}], lambda m, t: (n.append(1), call("1+1"))[1], max_steps=3)
        self.assertEqual(len(n), 3)
        self.assertIn("Stopped after 3", out)

    def test_tool_error_is_fed_back(self):
        script = [call("1/0"), {"role": "assistant", "content": "Cannot divide by zero."}]
        msgs = []

        def chat(messages, tools):
            msgs.append(list(messages))
            return script[len(msgs) - 1]

        run_agent([{"role": "user", "content": "1/0"}], chat)
        self.assertEqual(msgs[1][-1]["content"], "error: division by zero")

    def test_think_is_stripped(self):
        self.assertEqual(clean("let me see\n</think>\n\nIt is 395."), "It is 395.")
        self.assertEqual(clean("<think>x</think>ok"), "ok")
        self.assertEqual(clean("plain"), "plain")

    def test_emit_records_every_step(self):
        script = [call("2+2"), {"role": "assistant", "content": "4"}]
        n, events = [], []

        def chat(m, t):
            n.append(1)
            return script[len(n) - 1]

        run_agent([{"role": "user", "content": "2+2"}], chat, emit=events.append)
        self.assertEqual([e["type"] for e in events],
                         ["model_call", "model_reply", "tool_result", "model_call", "model_reply", "final"])
        self.assertEqual(events[2]["result"], "4")


class TraceTests(unittest.TestCase):
    def test_strip_trace_from_history(self):
        shown = TRACE_HEAD + " · request `a`\n>\n> - `step 1` x" + TRACE_END + "It is 4."
        self.assertEqual(strip_trace(shown), "It is 4.")
        self.assertEqual(strip_trace("plain"), "plain")

    def test_format_event(self):
        e = {"type": "tool_result", "step": 1, "tool": "calculator", "result": "395", "ms": 0}
        self.assertIn("returned `395`", format_event(e))


if __name__ == "__main__":
    unittest.main()
