import torch, time

# Kiểm tra GPU
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Using device:", device, torch.cuda.get_device_name(0))
print("Device Capability:", torch.cuda.get_device_capability(0))
print("Cudnn Version:",torch.backends.cudnn.version())  # xem cuDNN
print("Cudnn:",torch.backends.cudnn.enabled)    # True nếu dùng cuDNN


# Thiết lập kích thước tensor
N = 8192
a = torch.randn(N, N, device=device)
b = torch.randn(N, N, device=device)

# Làm nóng GPU (warmup)
for _ in range(5):
    torch.matmul(a, b)

# Benchmark GPU (FP32)
torch.cuda.synchronize()
t0 = time.time()
for _ in range(10):
    c = torch.matmul(a, b)
torch.cuda.synchronize()
t1 = time.time()
print(f"[FP32] GPU matmul: {(t1 - t0):.3f} sec")

# Benchmark Mixed Precision (FP16)
a_half = a.half()
b_half = b.half()

torch.cuda.synchronize()
t0 = time.time()
for _ in range(10):
    c_half = torch.matmul(a_half, b_half)
torch.cuda.synchronize()
t1 = time.time()
print(f"[FP16] GPU matmul: {(t1 - t0):.3f} sec")

# Benchmark CPU
a_cpu = a.cpu()
b_cpu = b.cpu()
t0 = time.time()
for _ in range(2):
    c_cpu = torch.matmul(a_cpu, b_cpu)
t1 = time.time()
print(f"CPU matmul: {(t1 - t0):.3f} sec")
