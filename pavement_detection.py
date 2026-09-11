"""Train, evaluate and run pavement-raveling segmentation and severity analysis."""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset, random_split

from cfds_lite_unet import CFDSLiteUNet, parameter_count

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def enhance_image(image_bgr: np.ndarray, clip_limit: float = 2.0) -> np.ndarray:
    """Paper-inspired CLAHE enhancement; works for RGB or replicated depth images."""
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    enhanced = cv2.merge((clahe.apply(l_channel), a_channel, b_channel))
    return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)


def build_initial_mask(gray: np.ndarray, threshold: int = 130) -> np.ndarray:
    """Generate initial labels using the paper's threshold/opening/closing settings."""
    # In the paper, lower depth-gray pixels are raveling and become white foreground.
    mask = np.where(gray < threshold, 255, 0).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((20, 20), np.uint8))
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))


def list_images(directory: Path) -> list[Path]:
    return sorted(p for p in directory.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)


class RavelingDataset(Dataset):
    def __init__(self, image_dir: Path, mask_dir: Path, size: int = 512, augment: bool = False):
        self.items = []
        for image_path in list_images(image_dir):
            matches = [mask_dir / f"{image_path.stem}{suffix}" for suffix in IMAGE_EXTENSIONS]
            mask_path = next((p for p in matches if p.exists()), None)
            if mask_path is not None:
                self.items.append((image_path, mask_path))
        if not self.items:
            raise ValueError(f"No matching image/mask pairs found in {image_dir} and {mask_dir}")
        self.size, self.augment = size, augment

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int):
        image_path, mask_path = self.items[index]
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if image is None or mask is None:
            raise ValueError(f"Unable to read {image_path} or {mask_path}")
        image = cv2.resize(enhance_image(image), (self.size, self.size), interpolation=cv2.INTER_LINEAR)
        mask = cv2.resize(mask, (self.size, self.size), interpolation=cv2.INTER_NEAREST)
        if self.augment:
            if random.random() < 0.5:
                image, mask = cv2.flip(image, 1), cv2.flip(mask, 1)
            if random.random() < 0.5:
                image, mask = cv2.flip(image, 0), cv2.flip(mask, 0)
        image = np.ascontiguousarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        mask = np.ascontiguousarray(mask)
        x = torch.from_numpy(image).permute(2, 0, 1).float() / 255.0
        y = torch.from_numpy((mask > 127).astype(np.float32))[None]
        return x, y, image_path.name


def confusion(logits: torch.Tensor, target: torch.Tensor, threshold: float = 0.5):
    pred = torch.sigmoid(logits) >= threshold
    truth = target >= 0.5
    dims = (1, 2, 3)
    tp = (pred & truth).sum(dims).float()
    fp = (pred & ~truth).sum(dims).float()
    fn = (~pred & truth).sum(dims).float()
    tn = (~pred & ~truth).sum(dims).float()
    return tp, fp, fn, tn


def metrics_from_counts(tp: float, fp: float, fn: float, tn: float) -> dict[str, float]:
    eps = 1e-7
    iou_fg = tp / (tp + fp + fn + eps)
    iou_bg = tn / (tn + fp + fn + eps)
    precision = tp / (tp + fp + eps)
    recall = tp / (tp + fn + eps)
    return {
        "iou": iou_fg,
        "miou": (iou_fg + iou_bg) / 2,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall + eps),
        "pixel_accuracy": (tp + tn) / (tp + fp + fn + tn + eps),
    }


@torch.inference_mode()
def evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> dict[str, float]:
    model.eval()
    totals = np.zeros(4, dtype=np.float64)
    for x, y, _ in loader:
        values = confusion(model(x.to(device)), y.to(device))
        totals += np.array([v.sum().item() for v in values])
    return metrics_from_counts(*totals)


def save_checkpoint(path: Path, model: nn.Module, epoch: int, metrics: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"model": model.state_dict(), "epoch": epoch, "metrics": metrics}, path)


def train(args) -> None:
    device = torch.device(args.device if args.device else ("cuda" if torch.cuda.is_available() else "cpu"))
    full = RavelingDataset(Path(args.images), Path(args.masks), args.size, augment=True)
    val_count = max(1, round(len(full) * args.val_ratio))
    train_count = len(full) - val_count
    if train_count < 1:
        raise ValueError("At least two image/mask pairs are required")
    generator = torch.Generator().manual_seed(args.seed)
    train_set, val_set = random_split(full, [train_count, val_count], generator=generator)
    # Validation must not use random augmentation.
    val_data = RavelingDataset(Path(args.images), Path(args.masks), args.size, augment=False)
    val_set = torch.utils.data.Subset(val_data, val_set.indices)
    train_loader = DataLoader(train_set, args.batch_size, shuffle=True, num_workers=args.workers)
    val_loader = DataLoader(val_set, args.batch_size, shuffle=False, num_workers=args.workers)
    model = CFDSLiteUNet().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    criterion = nn.BCEWithLogitsLoss()
    best = -1.0
    print(f"device={device}, train={train_count}, val={val_count}, parameters={parameter_count(model):,}")
    for epoch in range(1, args.epochs + 1):
        model.train()
        loss_sum = 0.0
        optimizer.zero_grad(set_to_none=True)
        for batch_index, (x, y, _) in enumerate(train_loader, start=1):
            x, y = x.to(device), y.to(device)
            loss = criterion(model(x), y)
            (loss / args.accumulation_steps).backward()
            if batch_index % args.accumulation_steps == 0 or batch_index == len(train_loader):
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
            loss_sum += loss.item() * x.shape[0]
        scores = evaluate(model, val_loader, device)
        print(f"epoch={epoch:03d} loss={loss_sum/train_count:.5f} " + " ".join(f"{k}={v:.4f}" for k, v in scores.items()))
        if scores["miou"] > best:
            best = scores["miou"]
            save_checkpoint(Path(args.output), model, epoch, scores)


def load_model(weights: Path, device: torch.device) -> nn.Module:
    model = CFDSLiteUNet().to(device)
    checkpoint = torch.load(weights, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint.get("model", checkpoint))
    model.eval()
    return model


def severity(area_cm2: float) -> str:
    if area_cm2 < 6.75:
        return "slight"
    if area_cm2 <= 8.5:
        return "moderate"
    return "severe"


@torch.inference_mode()
def predict(args) -> None:
    device = torch.device(args.device if args.device else ("cuda" if torch.cuda.is_available() else "cpu"))
    model = load_model(Path(args.weights), device)
    input_path, output_dir = Path(args.input), Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = list_images(input_path) if input_path.is_dir() else [input_path]
    rows = []
    for path in paths:
        original = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if original is None:
            print(f"skip unreadable file: {path}")
            continue
        enhanced = enhance_image(original)
        resized = cv2.resize(enhanced, (args.size, args.size), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        tensor = torch.from_numpy(rgb).permute(2, 0, 1).float()[None].to(device) / 255.0
        prob = torch.sigmoid(model(tensor))[0, 0].cpu().numpy()
        mask_small = (prob >= args.threshold).astype(np.uint8) * 255
        mask = cv2.resize(mask_small, (original.shape[1], original.shape[0]), interpolation=cv2.INTER_NEAREST)
        area_ratio = float((mask > 0).mean())
        area_cm2 = area_ratio * args.width_cm * args.height_cm
        level = severity(area_cm2)
        overlay = original.copy()
        color = np.zeros_like(original); color[:, :, 2] = mask
        overlay = cv2.addWeighted(overlay, 0.68, color, 0.32, 0)
        cv2.putText(overlay, f"area={area_cm2:.3f} cm2 | {level}", (18, 38),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
        cv2.imwrite(str(output_dir / f"{path.stem}_mask.png"), mask)
        cv2.imwrite(str(output_dir / f"{path.stem}_overlay.jpg"), overlay)
        rows.append({"image": path.name, "distress_pixels_ratio": area_ratio,
                     "distress_area_cm2": area_cm2, "severity": level})
    with (output_dir / "analysis.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["image", "distress_pixels_ratio", "distress_area_cm2", "severity"])
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps(rows, ensure_ascii=False, indent=2))


def prepare_masks(args) -> None:
    source, output = Path(args.images), Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for path in list_images(source):
        gray = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if gray is not None:
            cv2.imwrite(str(output / f"{path.stem}.png"), build_initial_mask(gray, args.threshold))
    print("Initial masks created. Review/correct them manually before training, as done by the paper's experts.")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CFDSLite-UNet pavement raveling detection")
    commands = parser.add_subparsers(dest="command", required=True)
    masks = commands.add_parser("prepare-masks", help="create initial masks from depth grayscale images")
    masks.add_argument("--images", required=True); masks.add_argument("--output", default="data/masks")
    masks.add_argument("--threshold", type=int, default=130); masks.set_defaults(func=prepare_masks)
    training = commands.add_parser("train", help="train the segmentation model")
    training.add_argument("--images", required=True); training.add_argument("--masks", required=True)
    training.add_argument("--output", default="runs/best.pt"); training.add_argument("--size", type=int, default=512)
    training.add_argument("--epochs", type=int, default=100); training.add_argument("--batch-size", type=int, default=4)
    training.add_argument("--accumulation-steps", type=int, default=1,
                          help="gradient accumulation; effective batch = batch-size * this value")
    training.add_argument("--lr", type=float, default=1e-4); training.add_argument("--weight-decay", type=float, default=1e-5)
    training.add_argument("--val-ratio", type=float, default=0.2); training.add_argument("--seed", type=int, default=42)
    training.add_argument("--workers", type=int, default=0); training.add_argument("--device")
    training.set_defaults(func=train)
    prediction = commands.add_parser("predict", help="segment and quantify raveling")
    prediction.add_argument("--input", required=True); prediction.add_argument("--weights", required=True)
    prediction.add_argument("--output", default="runs/predictions"); prediction.add_argument("--size", type=int, default=512)
    prediction.add_argument("--threshold", type=float, default=0.5)
    prediction.add_argument("--width-cm", type=float, default=10.2)
    prediction.add_argument("--height-cm", type=float, default=11.5); prediction.add_argument("--device")
    prediction.set_defaults(func=predict)
    return parser


if __name__ == "__main__":
    arguments = make_parser().parse_args()
    arguments.func(arguments)
