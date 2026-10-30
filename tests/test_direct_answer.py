import unittest

from orchestrator.direct_answer import DirectAnswerAgent, MARKER


class FakeClient:
    def __init__(self, reply):
        self.reply, self.prompts = reply, []

    def generate(self, prompt, **kw):
        self.prompts.append(prompt)
        return {"response": self.reply}


BODY = "Market Cap $350B\n" * 40


class DirectAnswerTests(unittest.TestCase):
    def test_answer_goes_on_top_and_sees_question_and_results(self):
        c = FakeClient("Mixed. Quant says +0.89% but confidence is 0.02%. Not financial advice.")
        out = DirectAnswerAgent(c).apply("Is INTC undervalued?", BODY)
        self.assertTrue(out.startswith(MARKER))
        self.assertTrue(out.endswith(BODY))
        self.assertIn("Is INTC undervalued?", c.prompts[0])
        self.assertIn("Market Cap $350B", c.prompts[0])

    def test_skips_commands_short_replies_and_repeats(self):
        c = FakeClient("x" * 50)
        a = DirectAnswerAgent(c)
        self.assertEqual(a.apply("/review", BODY), BODY)
        self.assertEqual(a.apply("hi?", "short"), "short")
        done = a.apply("Is INTC cheap?", BODY)
        self.assertEqual(a.apply("Is INTC cheap?", done), done)

    def test_failure_returns_original(self):
        class Boom:
            def generate(self, *a, **k):
                raise RuntimeError("down")
        self.assertEqual(DirectAnswerAgent(Boom()).apply("Is INTC cheap?", BODY), BODY)
        self.assertEqual(DirectAnswerAgent(FakeClient("")).apply("Is INTC cheap?", BODY), BODY)


if __name__ == "__main__":
    unittest.main()
