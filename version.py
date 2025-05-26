import torch

print("PyTorch version:", torch.__version__)
print("CUDA version (compiled):", torch.version.cuda)
print("cuDNN version:", torch.backends.cudnn.version())
print("Is GPU available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU name:", torch.cuda.get_device_name(0))
    print("CUDA runtime version (dynamic):", torch.version.cuda)
```
PyTorch version: 2.5.1
CUDA version (compiled): 12.1
cuDNN version: 90100
Is GPU available: True
GPU name: NVIDIA GeForce RTX 3090
CUDA runtime version (dynamic): 12.1
```