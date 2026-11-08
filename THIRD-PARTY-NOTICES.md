# Third-party software

The MIT license covers this project's original code. Bundled dependencies retain
their own licenses and copyright notices.

The Windows application includes CPython 3.11.15 and the packages listed in
`requirements-windows.lock`. Python's license is in `runtime/LICENSE.txt`;
package licenses are retained in `runtime/Lib/site-packages`, including each
package's `.dist-info` license files. `RUNTIME-VERSIONS.txt` records the build.
The Microsoft Visual C++ Redistributable installer retains Microsoft's license
and publisher signature. It is installed only when the required runtime is absent.

IBM Plex Sans and IBM Plex Mono are distributed under the SIL Open Font License.
Their notices are included beside the fonts in `ui/fonts` and `site/fonts`.

GPT-2 weights and tokenizer files are downloaded separately from
`openai-community/gpt2` on Hugging Face, at revision
`607a30d783dfa663caf39e06633721c8d4cfcd7e`. They are not included in the installer.
See the model repository for its MIT license and model documentation:
https://huggingface.co/openai-community/gpt2
