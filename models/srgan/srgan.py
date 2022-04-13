import argparse
import logging
import os
import random

import torch
import torch.backends.cudnn as cudnn
import torch.optim
import torch.utils.data
import torchvision.transforms as transforms
import torchvision.utils as vutils
from PIL import Image
from torchvision.transforms import InterpolationMode

from .srgan_pytorch import models as models
from .srgan_pytorch.utils.common import configure
from .srgan_pytorch.utils.common import create_folder
from .srgan_pytorch.utils.estimate import iqa
from .srgan_pytorch.utils.transform import process_image


class SRGAN:
    def __init__(
        self,
        arch="srgan_2x2",
        model_path="./weights/PSNR.pth",
        # pretrained=False,
        seed=666,
        gpu=0, # set None to use cpu
    ):
        # Save some params
        self.arch = arch
        self.model_path = model_path
        self.gpu = gpu
        self.seed = seed

        # Seed and / cuda Config
        self.model_names = sorted(name for name in models.__dict__ if name.islower() and not name.startswith("__") and callable(models.__dict__[name]))
        random.seed(seed)
        torch.manual_seed(seed)
        cudnn.deterministic = True

        # Load model
        self.model = models.__dict__[arch]()
        ''' 
        if pretrained:
            self.model = models.__dict__[arch](pretrained=True) # this crashes for latest implementations (model urls down)
        '''
        if os.path.exists(model_path):
            self.model.load_state_dict(torch.load(model_path,map_location=torch.device("cpu")))
        
        if gpu is not None:
            torch.cuda.set_device(gpu)
            self.model = self.model.cuda(gpu)

        # Set Eval mode
        self.model.eval()

        cudnn.benchmark = True
    
    def run_sr(self, img_file):
        print(f"Running SRGAN arch ({self.arch}) over {img_file}")
        lr = Image.open(img_file)
        lr = process_image(lr, self.gpu)
        with torch.no_grad():
            sr = self.model(lr)
        return sr

    def saveimage(self, img, path):
        vutils.save_image(img, path)