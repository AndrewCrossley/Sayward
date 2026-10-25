# Third-party software

Sayward bundles Python and open-source runtime dependencies. Original license texts and package metadata are included alongside the frozen runtime. Major components include Python (PSF), faster-whisper and CTranslate2 (MIT), PyAV/FFmpeg (their bundled license terms), NumPy (BSD), ONNX Runtime (MIT), sounddevice (MIT), pystray (LGPL) and Pillow (HPND).

Whisper model weights are downloaded separately from the selected Hugging Face model repository, not embedded in the installer. NVIDIA CUDA/cuDNN runtimes are optional user-installed Windows dependencies and retain NVIDIA's terms; no NVIDIA driver is installed by Sayward.
