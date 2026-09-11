from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = Path(r"Y:\jiaotong\output\docx\CFDSLite_UNet_GPU租赁训练指南.docx")
OUT.parent.mkdir(parents=True, exist_ok=True)

doc = Document()
sec = doc.sections[0]
sec.top_margin, sec.bottom_margin = Cm(2.1), Cm(2.0)
sec.left_margin, sec.right_margin = Cm(2.25), Cm(2.15)

styles = doc.styles
for name, size in [("Normal", 10.5), ("Title", 24), ("Subtitle", 11), ("Heading 1", 16), ("Heading 2", 12.5), ("Heading 3", 11)]:
    s = styles[name]
    s.font.name = "Microsoft YaHei"
    s._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    s.font.size = Pt(size)
    s.font.color.rgb = RGBColor(0, 0, 0)
styles["Normal"].paragraph_format.space_after = Pt(6)
styles["Normal"].paragraph_format.line_spacing = 1.25
styles["Heading 1"].paragraph_format.space_before = Pt(16)
styles["Heading 1"].paragraph_format.space_after = Pt(7)
styles["Heading 1"].paragraph_format.keep_with_next = True
styles["Heading 2"].paragraph_format.space_before = Pt(11)
styles["Heading 2"].paragraph_format.space_after = Pt(5)
styles["Heading 2"].paragraph_format.keep_with_next = True

def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = tcPr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd"); tcPr.append(shd)
    shd.set(qn("w:fill"), fill)

def borders(table):
    tblPr = table._tbl.tblPr
    elem = tblPr.first_child_found_in("w:tblBorders")
    if elem is None:
        elem = OxmlElement("w:tblBorders"); tblPr.append(elem)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = OxmlElement(f"w:{edge}")
        tag.set(qn("w:val"), "single"); tag.set(qn("w:sz"), "4")
        tag.set(qn("w:color"), "D9D9D9"); elem.append(tag)

def set_cell_margin(cell, top=100, start=120, bottom=100, end=120):
    tc = cell._tc; tcPr = tc.get_or_add_tcPr()
    tcMar = tcPr.first_child_found_in("w:tcMar")
    if tcMar is None:
        tcMar = OxmlElement("w:tcMar"); tcPr.append(tcMar)
    for m, v in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = OxmlElement(f"w:{m}"); node.set(qn("w:w"), str(v)); node.set(qn("w:type"), "dxa"); tcMar.append(node)

def table(headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER; t.autofit = False
    borders(t)
    trPr = t.rows[0]._tr.get_or_add_trPr()
    repeat = OxmlElement("w:tblHeader"); repeat.set(qn("w:val"), "true"); trPr.append(repeat)
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]; c.text = h; shade(c, "1F4E78")
        c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        for run in c.paragraphs[0].runs:
            run.font.bold = True; run.font.color.rgb = RGBColor(255,255,255); run.font.size = Pt(9)
        if widths: c.width = Cm(widths[i])
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = str(value); cells[i].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margin(cells[i])
            if widths: cells[i].width = Cm(widths[i])
            if ri % 2: shade(cells[i], "F2F6FA")
            for p in cells[i].paragraphs:
                p.paragraph_format.space_after = Pt(1); p.paragraph_format.line_spacing = 1.1
                for run in p.runs: run.font.size = Pt(8.6)
    doc.add_paragraph().paragraph_format.space_after = Pt(1)
    return t

def code(text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.45); p.paragraph_format.right_indent = Cm(0.25)
    p.paragraph_format.space_before = Pt(3); p.paragraph_format.space_after = Pt(7)
    p.paragraph_format.line_spacing = 1.05
    for line in text.strip().splitlines():
        r = p.add_run(line + "\n"); r.font.name = "Consolas"; r._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        r.font.size = Pt(8.5); r.font.color.rgb = RGBColor(25,25,25)
    pPr = p._p.get_or_add_pPr(); shd = OxmlElement("w:shd"); shd.set(qn("w:fill"), "F3F5F7"); pPr.append(shd)

def bullet(text, level=0):
    p = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
    p.add_run(text); p.paragraph_format.space_after = Pt(3)

def numbered(text):
    p = doc.add_paragraph(style="List Number"); p.add_run(text); p.paragraph_format.space_after = Pt(3)

# Cover
p = doc.add_paragraph(style="Title"); p.alignment = WD_ALIGN_PARAGRAPH.LEFT
p.add_run("CFDSLite UNet GPU租赁训练指南")
p = doc.add_paragraph(style="Subtitle")
p.add_run("路面松散像素级检测项目  从数据上传到模型下载")
doc.add_paragraph("适用项目目录：Y:\\jiaotong", style="Subtitle")
doc.add_paragraph("目标实例：NVIDIA V100 32 GB、4 核 CPU、55 GB 内存、150 GB 数据盘。", style="Subtitle")
doc.add_paragraph("版本：1.0    日期：2026年9月", style="Subtitle")
doc.add_paragraph("本指南面向第一次租用云端 GPU 的使用者。全部操作在租用服务器的终端中完成，包括代码建立、公开数据下载、数据检查、模型训练和结果打包。本地电脑只负责打开平台网页及最终下载结果。训练结果的可靠性首先取决于像素掩膜质量，正式训练前必须在服务器上完成数据配对和抽样检查。")

doc.add_heading("快速结论", level=1)
table(["项目", "建议"], [
    ["GPU", "截图中的 V100 32 GB 可直接使用；512×512、batch size 4 足够稳妥"],
    ["系统盘", "至少 30 GB；数据盘容量应不小于数据集解压后体积的 2 倍"],
    ["训练命令", "python pavement_detection.py train --images data/images --masks data/masks --output runs/best.pt"],
    ["默认参数", "512×512，Adam，学习率 1e-4，batch 4，100 epochs，weight decay 1e-5"],
    ["必须下载", "runs/best.pt、训练日志、数据划分记录；关机前确认文件已保存到持久化存储"],
], [3.0, 12.5])

doc.add_heading("一 实例选择与限制", level=1)
doc.add_heading("1.1 选择实例", level=2)
table(["显存", "适用设置", "评价"], [
    ["V100 32 GB", "512×512，batch 4", "当前实例。显存充足，适合完整训练；支持 CUDA，但 Tensor Core 代际较旧"],
    ["24 GB", "512×512，batch 4", "推荐。与当前代码默认参数匹配，通常无需改模型"],
    ["16 GB", "512×512，batch 2；必要时 384×384", "可以训练，但速度和论文复现一致性略受影响"],
    ["12 GB", "512×512，batch 1，或 384×384 batch 2", "仅适合试跑，不建议作为完整实验首选"],
    ["40 GB 及以上", "512×512，batch 4至8", "速度更快，但当前轻量模型通常没有必要"],
], [2.3, 5.1, 8.1])
doc.add_paragraph("截图中的 V100 32 GB、55 GB 内存和 150 GB 数据盘可以满足当前 CFDSLite-UNet。4 核 CPU 足够，但数据解码可能限制 GPU 利用率；建议 DataLoader workers 从 2 开始。按 1 元每小时计费时，应避免开机后才研究数据下载地址。平台应支持网页终端或 SSH，并确认数据盘在关机后是否保留。")
bullet("基础镜像选择 Ubuntu 22.04、CUDA 12.1 左右、PyTorch 2.x。")
bullet("实例开机前确认数据盘是否会在关机后保留；临时系统盘通常可能随实例释放而清空。")
bullet("不要购买多卡实例。当前代码是单卡训练，多卡不会自动加速。")

doc.add_heading("1.2 服务器目录规划", level=2)
doc.add_paragraph("所有内容放在数据盘中，不放在可能随实例释放而清空的系统盘。不同平台的数据盘挂载路径不同，先用 df -h 检查。下面以 /root/autodl-tmp 为例；如果平台路径不同，只需替换 PROJECT_ROOT。图像和掩膜必须同名，掩膜必须是二值图：白色表示松散，黑色表示背景。")
code(r"""/root/autodl-tmp/raveling/
  data/
    images/
      road_0001.png
      road_0002.png
    masks/
      road_0001.png
      road_0002.png""")
doc.add_paragraph("在云端终端建立目录：")
code("df -h\nexport PROJECT_ROOT=/root/autodl-tmp/raveling\nmkdir -p $PROJECT_ROOT/{data/images,data/masks,data/raw,runs}\ncd $PROJECT_ROOT\npwd")

doc.add_heading("二 终端获取代码和数据", level=1)
doc.add_heading("2.1 获取训练代码", level=2)
doc.add_paragraph("最稳定的全云端方式是把本项目代码放入私有 Git 仓库，再在服务器克隆。代码仓库只需包含 cfds_lite_unet.py、pavement_detection.py、requirements.txt 和 README.md，不要提交数据集或密钥。将下方地址替换为自己的仓库地址。")
code("export PROJECT_ROOT=/root/autodl-tmp/raveling\ngit clone https://github.com/你的账号/你的仓库.git $PROJECT_ROOT/code\ncd $PROJECT_ROOT/code\nln -sfn $PROJECT_ROOT/data data\npython -m py_compile cfds_lite_unet.py pavement_detection.py")
doc.add_paragraph("如果暂时没有 Git 仓库，可在平台的 Jupyter 文件区仅上传这 4 个很小的代码文件；数据集仍全部通过终端下载。不要在终端粘贴来源不明的安装脚本。")

doc.add_heading("2.2 直接下载 PaveSeg 预览集", level=2)
doc.add_paragraph("PaveSeg 的公开仓库包含 100 张像素级分割预览样本，适合验证训练流水线，但它不含松散类别，不能单独作为最终松散模型的数据。")
code("cd $PROJECT_ROOT/data/raw\ngit clone --depth 1 https://github.com/FuturePave/PaveSeg-Dataset.git paveseg\nfind paveseg -maxdepth 2 -type f | head\ndu -sh paveseg")

doc.add_heading("2.3 通过 Kaggle CLI 下载", level=2)
doc.add_paragraph("Kaggle 数据下载需要账号 API 凭据。先在 Kaggle 账户设置中创建 token，再把 kaggle.json 上传到服务器账户目录，或按平台安全方式设置 KAGGLE_USERNAME 和 KAGGLE_KEY。不要把 token 写入公开 Git 仓库。安装并下载后再解压到数据盘。")
code("python -m pip install -U kaggle\nmkdir -p ~/.kaggle\nchmod 600 ~/.kaggle/kaggle.json\ncd $PROJECT_ROOT/data/raw\n# 专门的松散检测竞赛数据；若竞赛要求接受规则，需先在网页完成\nkaggle competitions download -c cee-4803-fall-2022 -p raveling_kaggle\nunzip -q raveling_kaggle/*.zip -d raveling_kaggle/extracted\nfind raveling_kaggle/extracted -maxdepth 2 -type f | head\ndu -sh raveling_kaggle")
doc.add_paragraph("如果出现 401 或 403，通常是凭据无效、尚未接受竞赛规则或数据所有者限制访问，而不是命令错误。")

doc.add_heading("2.4 受限数据不能匿名下载", level=2)
doc.add_paragraph("EGY_PDD 最接近松散任务，包含 Raveling and Weathering、RGB、深度图和 PCD，但官方要求学术申请并签署协议，因此没有合法的匿名 wget 地址。获得作者授权和下载链接后，才能在服务器使用 wget 或 curl 下载。")
code("cd $PROJECT_ROOT/data/raw\nwget -c '作者授权后的下载链接' -O egy_pdd.zip\nunzip -q egy_pdd.zip -d egy_pdd")
doc.add_paragraph("不要使用来历不明的转载链接绕过授权。公开分割数据可以用于流程预训练，真正的松散分割仍需要 EGY_PDD 授权数据、论文作者数据或自采数据。")

doc.add_heading("三 初始化服务器", level=1)
doc.add_heading("3.1 检查 GPU", level=2)
code("nvidia-smi\npython --version\npython -c \"import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO GPU')\"")
doc.add_paragraph("最后一条命令应显示 True 和正确的 GPU 名称。如果显示 False，不要开始训练；应更换带 CUDA 的 PyTorch 镜像或安装与平台驱动兼容的 PyTorch。")
doc.add_heading("3.2 解压与创建环境", level=2)
code("export PROJECT_ROOT=/root/autodl-tmp/raveling\ncd $PROJECT_ROOT/code\npython -m venv .venv\nsource .venv/bin/activate\npython -m pip install --upgrade pip\npython -m pip install -r requirements.txt")
doc.add_paragraph("如果镜像已经预装可用的 GPU 版 PyTorch，执行 requirements.txt 时应留意 pip 是否把它替换为不兼容版本。安装后必须再次检查 CUDA：")
code("python -c \"import torch, cv2; print('torch=',torch.__version__,'cuda=',torch.cuda.is_available(),'opencv=',cv2.__version__)\"")

doc.add_heading("四 训练前质量检查", level=1)
doc.add_heading("4.1 检查数据数量", level=2)
code("cd $PROJECT_ROOT/code\nfind data/images -maxdepth 1 -type f | wc -l\nfind data/masks -maxdepth 1 -type f | wc -l\ndu -sh data")
doc.add_paragraph("图像数和掩膜数原则上应相同。当前程序会按文件主名配对；没有同名掩膜的图像会被忽略。")
doc.add_heading("4.2 生成初始掩膜", level=2)
doc.add_paragraph("若输入是与论文相似的深度灰度图，可以使用论文参数生成候选掩膜：")
code("python pavement_detection.py prepare-masks --images data/images --output data/masks --threshold 130")
doc.add_paragraph("这一步只产生预标注。至少随机查看 30 至 50 张掩膜，重点检查阴影误检、裂缝误检、松散区域漏标和掩膜黑白方向。普通 RGB 手机照片不宜盲目使用阈值 130。")
doc.add_heading("4.3 先做一分钟试跑", level=2)
doc.add_paragraph("正式训练前先运行 1 个 epoch，确认数据、显存和保存路径都正常。")
code("mkdir -p runs\npython pavement_detection.py train --images data/images --masks data/masks --output runs/smoke.pt --epochs 1 --batch-size 1 --workers 0")
doc.add_paragraph("试跑应打印 device=cuda、训练集数量、验证集数量、约 3,547,036 个参数，并在 runs 目录生成 smoke.pt。若 device=cpu，应停止并解决 CUDA 环境问题。")

doc.add_heading("五 正式训练", level=1)
doc.add_heading("5.1 推荐命令", level=2)
code("cd $PROJECT_ROOT/code\nsource .venv/bin/activate\nmkdir -p runs\npython -u pavement_detection.py train --images data/images --masks data/masks --output runs/best.pt --epochs 100 --batch-size 4 --lr 1e-4 --weight-decay 1e-5 --val-ratio 0.2 --workers 2 --device cuda 2>&1 | tee runs/train.log")
doc.add_paragraph("若平台的 CPU 核数较少或数据读取报错，将 --workers 4 改为 --workers 0。Windows 服务器也建议使用 0。")
doc.add_heading("5.2 有效 Batch size 20", level=2)
doc.add_paragraph("不建议在 V100 32 GB 上直接使用物理 batch 20。512×512 分割训练需要保存各层特征，直接设置 20 很可能触发 CUDA out of memory。使用物理 batch 4 并累计 5 次梯度，可得到有效 batch size 20，同时显存占用接近 batch 4。")
code("python -u pavement_detection.py train --images data/images --masks data/masks --output runs/best_bs20.pt --epochs 100 --batch-size 4 --accumulation-steps 5 --lr 1e-4 --weight-decay 1e-5 --val-ratio 0.2 --workers 2 --device cuda 2>&1 | tee runs/train_bs20.log")
doc.add_paragraph("梯度累积的有效 batch 20 与一次性物理 batch 20 数值上并非完全相同，但通常足够接近。论文原始设置是 batch 4；如果目标是复现论文，应先完成 batch 4 基线，再把有效 batch 20 作为独立对照实验。")
doc.add_heading("5.3 防止终端断开", level=2)
doc.add_paragraph("SSH 训练建议使用 tmux。关闭浏览器或网络断开后，训练仍会继续。")
code("tmux new -s raveling\n# 在 tmux 内执行正式训练命令\n# 临时离开：按 Ctrl+B，然后按 D\n# 重新连接：\ntmux attach -t raveling")
doc.add_heading("5.4 观察训练", level=2)
code("watch -n 2 nvidia-smi\ntail -f runs/train.log\nls -lh runs/best.pt")
table(["现象", "判断与操作"], [
    ["GPU 利用率长期接近 0%", "可能仍在 CPU 训练、数据读取过慢或进程已停止；检查日志和 torch.cuda.is_available()"],
    ["显存不足 CUDA out of memory", "先把 batch size 从 4 改为 2，再改为 1；仍不足则把 size 改为 384"],
    ["loss 下降且 mIoU 上升", "训练正常。best.pt 会在验证 mIoU 创新高时覆盖保存"],
    ["mIoU 很高但现场效果差", "可能存在同一路段数据泄漏、标签由模型自生成或数据来源单一"],
], [5.2, 10.3])

doc.add_heading("六 训练完成后的验证", level=1)
doc.add_heading("6.1 运行预测", level=2)
code("python pavement_detection.py predict --input data/test --weights runs/best.pt --output runs/predictions --device cuda")
doc.add_paragraph("默认扫描幅面为 10.2×11.5 cm，仅适用于论文对应的固定尺度数据。如果图片覆盖范围不同，应传入真实宽度和高度：")
code("python pavement_detection.py predict --input data/test --weights runs/best.pt --output runs/predictions --width-cm 50 --height-cm 40 --device cuda")
doc.add_heading("6.2 检查输出", level=2)
bullet("每张图应生成 *_mask.png，白色区域为预测的松散区域。")
bullet("每张图应生成 *_overlay.jpg，用红色叠加预测区域。")
bullet("analysis.csv 应包含松散像素比例、实际面积和轻度、中度、重度等级。")
bullet("随机查看至少 50 张预测结果，并单独记录漏检和误检，不能只看总体指标。")

doc.add_heading("七 下载和备份", level=1)
doc.add_paragraph("关机前至少保存模型、日志和预测结果。若平台的数据盘不是永久盘，应先下载到本地。")
code("cd $PROJECT_ROOT/code\ntar -czf raveling_results.tar.gz runs/best.pt runs/train.log runs/predictions")
doc.add_paragraph("从本地 PowerShell 下载，替换实际连接信息：")
code(r"scp -P 你的端口 用户名@服务器地址:/root/autodl-tmp/raveling/code/raveling_results.tar.gz 下载目录")
doc.add_paragraph("下载后在本地确认压缩包大小不为零且能够解压，再停止或释放实例。镜像保存不能替代结果下载；不同平台对镜像、系统盘和数据盘的保留规则不同。")

doc.add_heading("八 费用和时间控制", level=1)
numbered("在本地完成文件配对、掩膜抽查和代码语法检查后再开机。")
numbered("租卡后先做 1 epoch 试跑；只有确认 GPU、保存路径和指标正常，才开始 100 epochs。")
numbered("用前 10 至 20 epochs 判断是否学习。如果 loss 不降或掩膜方向错误，应尽早停止。")
numbered("训练结束立即压缩并下载产物；确认下载成功后再关机。")
numbered("如果平台按开机时间计费，训练进程结束并不等于实例自动停止。")

doc.add_heading("九 常见问题", level=1)
table(["报错或问题", "解决方法"], [
    ["ModuleNotFoundError", "确认已 source .venv/bin/activate，并执行 python -m pip install -r requirements.txt"],
    ["torch.cuda.is_available() 为 False", "使用带 CUDA 的 PyTorch 镜像；根据平台驱动版本安装官方兼容构建，不要继续 CPU 训练"],
    ["No matching image mask pairs", "确保 data/images 与 data/masks 中文件主名一致，例如 road_01.jpg 对应 road_01.png"],
    ["DataLoader worker exited", "把 --workers 改为 0；再检查是否有损坏图片"],
    ["CUDA out of memory", "降低 batch size；关闭占用 GPU 的其他进程；必要时降低输入 size"],
    ["预测面积不可信", "只有像素比例可信；实际 cm² 需要固定扫描幅面、标尺、相机标定或深度设备数据"],
    ["模型只预测背景", "检查正样本比例和掩膜方向；增加松散样本；避免背景数量压倒正样本"],
    ["模型把阴影当松散", "加入阴影困难负样本，修正相关标签，并使用现场图像进行微调"],
], [5.0, 10.5])

doc.add_heading("十 推荐实验记录", level=1)
doc.add_paragraph("每次正式训练复制下面信息到实验记录中。没有记录的模型很难比较，也无法可靠复现。")
table(["字段", "记录内容"], [
    ["实验编号", "例如 EXP 001"], ["GPU 与显存", "例如 RTX 4090 24 GB"],
    ["数据版本", "样本总数、各来源数量、掩膜版本"], ["数据划分", "训练和验证比例、随机种子、是否按道路或采集批次隔离"],
    ["训练参数", "size、batch、epochs、lr、weight decay"], ["最佳结果", "epoch、mIoU、F1、Recall、Pixel Accuracy"],
    ["模型文件", "best.pt 的路径、大小和校验值"], ["现场观察", "主要漏检、误检和下一轮改进"],
], [4.2, 11.3])

doc.add_heading("十一 完成检查表", level=1)
for item in [
    "图像和掩膜可以按文件主名一一配对",
    "随机抽查的掩膜黑白方向正确",
    "nvidia-smi 能识别租用的 GPU",
    "torch.cuda.is_available() 返回 True",
    "1 epoch 试跑成功并生成 smoke.pt",
    "正式训练日志已保存到 runs/train.log",
    "best.pt 已生成且大小不为零",
    "预测掩膜和叠加图已经人工抽查",
    "模型、日志和预测结果已经下载到本地",
    "确认下载文件可用后已停止计费实例",
]:
    bullet("□ " + item)

doc.add_page_break()
doc.add_heading("附录 当前项目关键参数", level=1)
doc.add_paragraph("当前实现依据 Peng 等提出的 CFDSLite-UNet：四层编码与解码、每个块两层深度可分离卷积、双线性插值上采样、BCEWithLogitsLoss 和 Adam。模型约 3.55 M 参数。论文报告的精度不能在缺少其原始数据和专家终审标签时直接视为本项目结果，应以自己的独立测试集重新测量。")
table(["参数", "默认值"], [
    ["输入尺寸", "512×512"], ["训练和验证", "80% 和 20%"], ["优化器", "Adam"],
    ["学习率", "1×10^-4"], ["Batch size", "4"], ["Epochs", "100"],
    ["Weight decay", "1×10^-5"], ["数据增强", "水平翻转和垂直翻转"],
], [5.0, 10.5])

# Footer page number field
for section in doc.sections:
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer.add_run("第 ")
    fld = OxmlElement("w:fldSimple"); fld.set(qn("w:instr"), "PAGE")
    run._r.addnext(fld)
    footer.add_run(" 页")
    for r in footer.runs: r.font.size = Pt(8); r.font.color.rgb = RGBColor(100,100,100)

doc.core_properties.title = "CFDSLite UNet GPU租赁训练指南"
doc.core_properties.subject = "路面松散检测模型云端GPU训练操作手册"
doc.core_properties.author = ""
doc.save(OUT)
print(OUT)
