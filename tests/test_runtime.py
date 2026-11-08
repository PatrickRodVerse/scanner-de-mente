from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lab.runtime import check_memory, download_model


class RuntimeTests(unittest.TestCase):
    def test_memory_guard_rejects_low_ram(self):
        with patch("psutil.virtual_memory") as memory:
            memory.return_value.available = 2 * 1024**3
            with self.assertRaisesRegex(RuntimeError, "No model was loaded"):
                check_memory()

    def test_complete_cache_does_not_access_network(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("config.json", "model.safetensors", "tokenizer.json",
                         "tokenizer_config.json", "vocab.json", "merges.txt"):
                (Path(directory) / name).touch()
            with patch("huggingface_hub.snapshot_download", return_value=directory) as download:
                self.assertEqual(download_model(), directory)
            self.assertEqual(download.call_count, 1)
            self.assertTrue(download.call_args.kwargs["local_files_only"])


if __name__ == "__main__":
    unittest.main()
