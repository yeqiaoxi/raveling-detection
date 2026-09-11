"""Eight-class PaveSeg training and prediction with CFDSLite-UNet."""
from __future__ import annotations
import argparse, csv, random
from pathlib import Path
import cv2
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset, random_split
from cfds_lite_unet import CFDSLiteUNet, parameter_count

GRAY_TO_CLASS = {0: 0, 30: 1, 60: 2, 90: 3, 120: 4, 150: 5, 180: 6, 210: 7}
CLASS_NAMES = ["background", "crack", "pothole", "sealed_crack", "patch",
               "alligator_crack", "utility_cover", "expansion_joint"]
PALETTE = np.array([[0,0,0],[255,80,80],[255,170,0],[255,255,0],[70,130,255],
                    [220,50,220],[80,220,220],[80,220,100]], dtype=np.uint8)

class PaveSegDataset(Dataset):
    def __init__(self, root: Path, size=512, augment=False):
        self.image_dir, self.mask_dir = root / "img_preview", root / "label_preview"
        self.items = []
        for image in sorted(self.image_dir.glob("*.jpg")):
            mask = self.mask_dir / f"{image.stem}_mask.png"
            if mask.exists(): self.items.append((image, mask))
        if not self.items: raise ValueError(f"No PaveSeg pairs found under {root}")
        self.size, self.augment = size, augment
    def __len__(self): return len(self.items)
    def __getitem__(self, i):
        ip, mp = self.items[i]
        image, gray = cv2.imread(str(ip)), cv2.imread(str(mp), cv2.IMREAD_GRAYSCALE)
        image = cv2.resize(image, (self.size,self.size), interpolation=cv2.INTER_LINEAR)
        gray = cv2.resize(gray, (self.size,self.size), interpolation=cv2.INTER_NEAREST)
        mask = np.full(gray.shape, 255, np.uint8)
        for value, cls in GRAY_TO_CLASS.items(): mask[gray == value] = cls
        if (mask == 255).any(): raise ValueError(f"Unknown grayscale label in {mp}")
        if self.augment and random.random() < .5: image, mask = cv2.flip(image,1), cv2.flip(mask,1)
        if self.augment and random.random() < .5: image, mask = cv2.flip(image,0), cv2.flip(mask,0)
        image = np.ascontiguousarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        return torch.from_numpy(image).permute(2,0,1).float()/255, torch.from_numpy(np.ascontiguousarray(mask)).long(), ip.name

def scores(conf):
    tp=np.diag(conf); union=conf.sum(0)+conf.sum(1)-tp
    iou=np.divide(tp,union,out=np.full(8,np.nan),where=union>0)
    return {"miou":float(np.nanmean(iou)), "pixel_accuracy":float(tp.sum()/max(conf.sum(),1)),
            **{f"iou_{CLASS_NAMES[i]}":float(iou[i]) for i in range(8)}}

@torch.inference_mode()
def evaluate(model, loader, device):
    model.eval(); conf=np.zeros((8,8),np.int64)
    for x,y,_ in loader:
        pred=model(x.to(device)).argmax(1).cpu().numpy(); truth=y.numpy()
        bins=np.bincount((truth*8+pred).ravel(),minlength=64).reshape(8,8); conf+=bins
    return scores(conf)

def train(a):
    device=torch.device(a.device if a.device else ("cuda" if torch.cuda.is_available() else "cpu"))
    base=PaveSegDataset(Path(a.data),a.size,True); clean=PaveSegDataset(Path(a.data),a.size,False)
    nv=max(1,round(len(base)*a.val_ratio)); nt=len(base)-nv
    tr,va=random_split(base,[nt,nv],generator=torch.Generator().manual_seed(a.seed))
    va=torch.utils.data.Subset(clean,va.indices)
    tl=DataLoader(tr,a.batch_size,shuffle=True,num_workers=a.workers,pin_memory=device.type=="cuda")
    vl=DataLoader(va,a.batch_size,num_workers=a.workers,pin_memory=device.type=="cuda")
    model=CFDSLiteUNet(num_classes=8).to(device); opt=torch.optim.Adam(model.parameters(),lr=a.lr,weight_decay=1e-5)
    loss_fn=nn.CrossEntropyLoss(); best=-1.; Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    print(f"device={device} train={nt} val={nv} parameters={parameter_count(model):,}")
    for epoch in range(1,a.epochs+1):
        model.train(); total=0.; opt.zero_grad(set_to_none=True)
        for bi,(x,y,_) in enumerate(tl,1):
            x,y=x.to(device),y.to(device); loss=loss_fn(model(x),y)
            (loss/a.accumulation_steps).backward(); total+=loss.item()*x.size(0)
            if bi%a.accumulation_steps==0 or bi==len(tl): opt.step(); opt.zero_grad(set_to_none=True)
        m=evaluate(model,vl,device); print(f"epoch={epoch:03d} loss={total/nt:.5f} miou={m['miou']:.4f} acc={m['pixel_accuracy']:.4f}")
        if m["miou"]>best: best=m["miou"]; torch.save({"model":model.state_dict(),"metrics":m,"classes":CLASS_NAMES},a.output)

@torch.inference_mode()
def predict(a):
    device=torch.device(a.device if a.device else ("cuda" if torch.cuda.is_available() else "cpu"))
    model=CFDSLiteUNet(num_classes=8).to(device); ck=torch.load(a.weights,map_location=device,weights_only=False); model.load_state_dict(ck["model"]); model.eval()
    out=Path(a.output); out.mkdir(parents=True,exist_ok=True); paths=sorted(Path(a.input).glob("*.jpg")) if Path(a.input).is_dir() else [Path(a.input)]
    rows=[]
    for p in paths:
        bgr=cv2.imread(str(p)); h,w=bgr.shape[:2]; small=cv2.resize(bgr,(a.size,a.size)); rgb=cv2.cvtColor(small,cv2.COLOR_BGR2RGB)
        x=torch.from_numpy(rgb).permute(2,0,1).float()[None].to(device)/255
        pred=model(x).argmax(1)[0].cpu().numpy().astype(np.uint8); pred=cv2.resize(pred,(w,h),interpolation=cv2.INTER_NEAREST)
        color=PALETTE[pred][:,:,::-1]; overlay=cv2.addWeighted(bgr,.6,color,.4,0); cv2.imwrite(str(out/f"{p.stem}_classes.png"),color); cv2.imwrite(str(out/f"{p.stem}_overlay.jpg"),overlay)
        row={"image":p.name}; row.update({CLASS_NAMES[i]:float((pred==i).mean()) for i in range(8)}); rows.append(row)
    with (out/"class_ratios.csv").open("w",newline="",encoding="utf-8-sig") as f: wr=csv.DictWriter(f,fieldnames=["image"]+CLASS_NAMES); wr.writeheader(); wr.writerows(rows)

def parser():
    p=argparse.ArgumentParser(); s=p.add_subparsers(dest="cmd",required=True)
    t=s.add_parser("train"); t.add_argument("--data",required=True); t.add_argument("--output",default="runs/paveseg_best.pt"); t.add_argument("--size",type=int,default=512); t.add_argument("--epochs",type=int,default=100); t.add_argument("--batch-size",type=int,default=4); t.add_argument("--accumulation-steps",type=int,default=1); t.add_argument("--lr",type=float,default=1e-4); t.add_argument("--val-ratio",type=float,default=.2); t.add_argument("--seed",type=int,default=42); t.add_argument("--workers",type=int,default=2); t.add_argument("--device"); t.set_defaults(func=train)
    q=s.add_parser("predict"); q.add_argument("--input",required=True); q.add_argument("--weights",required=True); q.add_argument("--output",default="runs/paveseg_predictions"); q.add_argument("--size",type=int,default=512); q.add_argument("--device"); q.set_defaults(func=predict)
    return p
if __name__=="__main__": a=parser().parse_args(); a.func(a)
