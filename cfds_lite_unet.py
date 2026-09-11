"""CFDSLite-UNet implementation based on Peng et al. (2026)."""

from __future__ import annotations

import torch
from torch import nn
import torch.nn.functional as F


class SeparableConv(nn.Module):
    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.depthwise = nn.Conv2d(
            in_channels, in_channels, 3, padding=1, groups=in_channels, bias=False
        )
        self.pointwise = nn.Conv2d(in_channels, out_channels, 1, bias=False)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.relu(self.pointwise(self.depthwise(x)))


class SeparableConvBlock(nn.Module):
    """Two 3x3 depthwise-separable convolutions, as specified in Table 4."""

    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.block = nn.Sequential(
            SeparableConv(in_channels, out_channels),
            SeparableConv(out_channels, out_channels),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class CFDSLiteUNet(nn.Module):
    def __init__(self, in_channels: int = 3, base_channels: int = 64, num_classes: int = 1) -> None:
        super().__init__()
        c = base_channels
        self.enc1 = SeparableConvBlock(in_channels, c)
        self.enc2 = SeparableConvBlock(c, c * 2)
        self.enc3 = SeparableConvBlock(c * 2, c * 4)
        self.enc4 = SeparableConvBlock(c * 4, c * 8)
        self.bottleneck = SeparableConvBlock(c * 8, c * 16)
        self.dec4 = SeparableConvBlock(c * 24, c * 8)
        self.dec3 = SeparableConvBlock(c * 12, c * 4)
        self.dec2 = SeparableConvBlock(c * 6, c * 2)
        self.dec1 = SeparableConvBlock(c * 3, c)
        self.head = nn.Conv2d(c, num_classes, 1)
        self.pool = nn.MaxPool2d(2)

    @staticmethod
    def _up(x: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        x = F.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
        return torch.cat((x, skip), dim=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.enc4(self.pool(e3))
        x = self.bottleneck(self.pool(e4))
        x = self.dec4(self._up(x, e4))
        x = self.dec3(self._up(x, e3))
        x = self.dec2(self._up(x, e2))
        x = self.dec1(self._up(x, e1))
        return self.head(x)  # logits; apply sigmoid only for inference


def parameter_count(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
