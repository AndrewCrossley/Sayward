# Third-party software

Sayward bundles Python and open-source runtime dependencies. Original license texts and package metadata are included alongside the frozen runtime. Major components include Python (PSF), faster-whisper and CTranslate2 (MIT), PyAV/FFmpeg (their bundled license terms), NumPy (BSD), ONNX Runtime (MIT), sounddevice (MIT), pystray (LGPL) and Pillow (HPND).

Whisper model weights are downloaded separately from the selected Hugging Face model repository, not embedded in the installer. NVIDIA CUDA/cuDNN runtimes are optional user-installed Windows dependencies and retain NVIDIA's terms; no NVIDIA driver is installed by Sayward.
# Local punctuation weights

Explicit setup downloads Horizon-Labs/punctuation-restoration-small, revision b76fda22746a0f7778594493f0ad50f82dc4ae8a, from its author on Hugging Face. The model card declares Apache-2.0; base model mmBERT-small is MIT. The ONNX model, tokenizer and config are pinned and SHA-256 verified. These weights are not bundled into the installer. Source/model card: https://huggingface.co/Horizon-Labs/punctuation-restoration-small. License: https://www.apache.org/licenses/LICENSE-2.0.
