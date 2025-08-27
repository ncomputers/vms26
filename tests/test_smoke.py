import pytest


def test_gpu_tensor_operation():
    import torch

    if not torch.cuda.is_available():
        pytest.skip("CUDA is not available")

    x = torch.tensor([1.0], device="cuda")
    y = torch.tensor([2.0], device="cuda")
    result = x + y
    assert result.item() == 3.0
