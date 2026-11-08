import unittest

import torch
from transformers import GPT2Config, GPT2LMHeadModel

from lab.hooks import capture, patch
from lab.patching import recovery


class PatchingTests(unittest.TestCase):
    def test_tiny_gpt2_controls_and_hook_cleanup(self):
        torch.manual_seed(0)
        torch.set_num_threads(1)
        model = GPT2LMHeadModel(GPT2Config(vocab_size=32, n_positions=8, n_embd=16,
                                         n_layer=2, n_head=2, attn_pdrop=0,
                                         resid_pdrop=0, embd_pdrop=0)).eval()
        clean, corrupt = torch.tensor([[1, 2, 3]]), torch.tensor([[4, 4, 5]])
        with torch.inference_mode():
            with capture(model.transformer.h) as states:
                expected = model(clean, use_cache=False).logits[:, -1]
            baseline = model(corrupt, use_cache=False).logits[:, -1]
            with patch(model.transformer.h[-1], -1, states[1][:, -1]):
                restored = model(corrupt, use_cache=False).logits[:, -1]
            torch.testing.assert_close(restored, expected)
            with patch(model.transformer.h[-1], 0, states[1][:, 0]):
                unchanged = model(corrupt, use_cache=False).logits[:, -1]
            torch.testing.assert_close(unchanged, baseline)
            with self.assertRaisesRegex(RuntimeError, "sentinel"):
                with patch(model.transformer.h[0], 0, states[0][:, 0]):
                    raise RuntimeError("sentinel")
        self.assertTrue(all(not block._forward_hooks for block in model.transformer.h))

    def test_recovery_can_be_negative_or_above_one(self):
        self.assertIsNone(recovery(1, 1, 1))
        self.assertEqual(recovery(3, 2, 0), 1.5)
        self.assertEqual(recovery(-1, 2, 0), -0.5)


if __name__ == "__main__":
    unittest.main()
