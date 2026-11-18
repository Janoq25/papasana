"""Comprueba ejecución CUDA real y guarda evidencia de dispositivo, tiempo y memoria."""
import argparse
import json
import time
from pathlib import Path

import torch

import potato_blight
from potato_blight.models import build_model


def check(output: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA no está disponible. Este entrenamiento exige GPU.")
    torch.set_num_threads(4)
    dev = torch.device("cuda:0")
    torch.cuda.reset_peak_memory_stats()
    model = build_model("resnet50", 3, pretrained=False).to(dev).train()
    x = torch.randn(8, 3, 224, 224, device=dev)
    y = torch.tensor([0, 1, 2, 0, 1, 2, 0, 1], device=dev)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    scaler = torch.amp.GradScaler()
    torch.cuda.synchronize()
    start = time.perf_counter()
    for _ in range(3):
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast("cuda"):
            loss = torch.nn.functional.cross_entropy(model(x), y)
        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()
    torch.cuda.synchronize()
    result = {"cwd": str(Path.cwd()), "package": potato_blight.__file__, "torch": torch.__version__,
              "cuda_runtime": torch.version.cuda, "cuda_available": True,
              "gpu": torch.cuda.get_device_name(0),
              "vram_mb": torch.cuda.get_device_properties(0).total_memory / 1024**2,
              "model_device": str(next(model.parameters()).device), "input_device": str(x.device),
              "loss_device": str(loss.device), "training_steps": 3,
              "seconds": time.perf_counter() - start,
              "peak_allocated_mb": torch.cuda.max_memory_allocated() / 1024**2}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/gpu-check.json"))
    print(json.dumps(check(parser.parse_args().output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
