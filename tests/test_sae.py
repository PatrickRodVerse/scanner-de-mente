import unittest
import warnings

import torch

from lab.sae import SparseAutoencoder, split_contexts, train_sae, validate_cache


class SparseAutoencoderTests(unittest.TestCase):
    def test_small_training_is_deterministic_and_improves_reconstruction(self):
        generator = torch.Generator().manual_seed(9)
        activations = torch.randn(80, 8, generator=generator)
        contexts = [f"independent example {index}" for index in range(80)]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model, metrics, top = train_sae(activations, contexts, features=12, steps=80, batch_size=32)
            repeat, repeat_metrics, _ = train_sae(activations, contexts, features=12, steps=80, batch_size=32)
        self.assertLess(metrics["train_final"]["reconstruction_mse"], metrics["train_initial"]["reconstruction_mse"])
        self.assertEqual(metrics, repeat_metrics)
        self.assertEqual(metrics["split"], "distinct_context_groups")
        self.assertGreater(metrics["holdout_rows"], 0)
        self.assertTrue(torch.allclose(model.decoder.weight.norm(dim=0), torch.ones(12), atol=1e-6))
        reconstructed, encoded = model(activations)
        self.assertTrue(torch.isfinite(reconstructed).all())
        self.assertTrue((encoded >= 0).all())
        for key, value in model.state_dict().items():
            self.assertTrue(torch.equal(value, repeat.state_dict()[key]))
        self.assertTrue(all(item["semantic_label"] is None for item in top))
        self.assertTrue(0 <= metrics["holdout"]["mean_l0"] <= 12)
        self.assertTrue(0 <= metrics["holdout"]["dead_fraction"] <= 1)

    def test_invalid_cache_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_cache(torch.tensor([[float("nan")], [0.0]]), ["a", "b"])
        with self.assertRaises(ValueError):
            validate_cache(torch.ones(2, 4), ["missing"])
        with self.assertRaises(ValueError):
            SparseAutoencoder(8, 0)

    def test_source_sentence_groups_do_not_cross_holdout(self):
        groups = [f"sentence {i // 4}" for i in range(40)]
        train, holdout, _ = split_contexts(groups, torch.Generator().manual_seed(0))
        self.assertFalse({groups[i] for i in train.tolist()} & {groups[i] for i in holdout.tolist()})


if __name__ == "__main__":
    unittest.main()
