# 路面松散灾害检测（CFDSLite-UNet）

这是依据 Peng 等（2026）论文实现的沥青路面松散（raveling）像素级检测与定量分析代码。它实现了论文中的 CLAHE、阈值与形态学初始标注、深度可分离卷积 U-Net、双线性插值上采样、BCE 损失、评价指标以及按实际扫描面积计算灾害等级。

## 云端获取项目

仓库推送到 GitHub 或 Gitee 后，可在 GPU 服务器终端直接执行：

```bash
git clone <你的仓库地址> raveling-detection
cd raveling-detection
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

训练数据、模型权重、日志、PDF 论文及账号密钥默认不会提交到 Git 仓库。

## PaveSeg 多病害分割

公开预览集包含背景、裂缝、坑槽、封缝、修补、龟裂、井盖和伸缩缝八个类别。下载并训练：

```bash
mkdir -p data/raw
git clone --depth 1 https://github.com/FuturePave/PaveSeg-Dataset.git data/raw/paveseg
python paveseg_training.py train --data data/raw/paveseg --output runs/paveseg_best.pt --device cuda
```

有效 batch size 20 使用梯度累积：

```bash
python paveseg_training.py train --data data/raw/paveseg --output runs/paveseg_bs20.pt --batch-size 4 --accumulation-steps 5 --device cuda
```

## 云端获取项目

仓库推送到 GitHub 或 Gitee 后，可在 GPU 服务器终端直接执行：

```bash
git clone <你的仓库地址> raveling-detection
cd raveling-detection
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

训练数据、模型权重、日志、PDF 论文及账号密钥默认不会提交到 Git 仓库。

> 论文没有公开训练数据和权重，因此本项目不能凭空复现论文报告的 mIoU=0.96；需使用你自己的深度图和人工校正掩膜训练。

## 数据目录

```text
data/
  images/       # 原图；支持 png/jpg/bmp/tif
  masks/        # 同名二值掩膜，白色=松散，黑色=背景
```

论文使用 LS-40 设备采集 2592×2048 深度图，实际幅面为 11.5×10.2 cm。普通路面 RGB 图也能输入，但和论文的数据域不同，精度需重新验证。

## 安装

```powershell
python -m pip install -r requirements.txt
```

## 1. 生成初始标注

```powershell
python pavement_detection.py prepare-masks --images data/images --output data/masks
```

默认使用论文参数：阈值 130、20×20 开运算、25×25 闭运算。论文随后由 4 名专家逐像素复核并以 3/4 投票形成最终标签，所以生成的掩膜务必人工检查，不应直接视为真值。

## 2. 训练

```powershell
python pavement_detection.py train --images data/images --masks data/masks --output runs/best.pt
```

默认复现论文训练参数：512×512、训练/验证 8:2、Adam、学习率 1e-4、batch 4、100 epochs、weight decay 1e-5，以及水平/垂直翻转。

如果需要有效 batch size 20，但显存无法直接容纳，可使用物理 batch 4、梯度累积 5 次：

```powershell
python pavement_detection.py train --images data/images --masks data/masks --output runs/best.pt --batch-size 4 --accumulation-steps 5
```

这会得到有效 batch size 20，但它不是论文原始的 batch 4 设置。

## 3. 检测与定量分析

```powershell
python pavement_detection.py predict --input data/test --weights runs/best.pt --output runs/predictions
```

输出每张图的二值掩膜、红色叠加图和 `analysis.csv`。默认按 10.2×11.5 cm 的扫描幅面计算松散面积，并采用论文分级：轻度 `<6.75 cm²`，中度 `6.75–8.5 cm²`，重度 `>8.5 cm²`。如果你的拍摄/扫描幅面不同，必须传入真实尺寸：

```powershell
python pavement_detection.py predict --input example.png --weights runs/best.pt --width-cm 50 --height-cm 40
```

## 与论文的一致性和差异

- 一致：网络各层通道、两层深度可分离卷积块、4 次池化、跳连、双线性上采样、单通道 logits、BCE、CLAHE、训练超参数、IoU/mIoU/Precision/Recall/F1/Pixel Accuracy。
- 必要差异：论文未给出 CLAHE 的 `clipLimit/tileGridSize`，实现采用 OpenCV 常用值 2.0/8×8；可按自有数据调参。
- 工程保护：模型输出 logits，训练使用数值稳定的 `BCEWithLogitsLoss`，预测时再 sigmoid。
