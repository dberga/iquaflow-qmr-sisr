import os
import numpy as np
from PIL import Image

import torch
import torch.nn as nn

#from .utils import load_img
from .EDSR.edsr import EDSR
from .modules import DSN
#from .adaptive_gridsampler.gridsampler import Downsampler

import numpy as np
import kornia
import torchvision.transforms as transforms

import sys
sys.path.append("../..")
from custom_transforms import blur_image, rescale_image

class CAR:
    def __init__(
        self,
        SCALE=2, 
        #model_dir="./models",
        #gpu=0,
    ):
        # Save some params
        #self.model_dir = model_dir
        #self.gpu = gpu

        # Load Downsampler kernel characteristics
        self.SCALE = SCALE
        self.KSIZE = 3 * SCALE + 1
        self.OFFSET_UNIT = SCALE

        # Load nets
        ''' # set to S3Loader
        self.downsampler_net = load_car_downsampler(model_dir, SCALE, KSIZE)
        self.upscale_net = load_car_model(model_dir, SCALE)
        self.kernel_generation_net = load_car_kgn(model_dir, SCALE, KSIZE)
        '''
    
    def run_upscale_mod(self, img_file, rescale = False, zoom = None, blur = False):

        img = load_img(img_file)

        if blur is True:
            img = blur_image(img, zoom)

        if rescale is not False:
            img = rescale_image(img, zoom)

        reconstructed_img = self.upscale_net(img)
        return reconstructed_img

    def run_upscale(self, img_file):
        img = load_img(img_file)
        reconstructed_img = self.upscale_net(img)
        return reconstructed_img
    '''
    def run_downscale(self, img_file):
        print(f"Running CAR downscale network over {img_file}")
        img = load_img(img_file)
        kernels, offsets_h, offsets_v = self.kernel_generation_net(img)
        downscaled_img = self.downsampler_net(img, kernels, offsets_h, offsets_v, OFFSET_UNIT)
        return downscaled_img
    '''
    def run_upscale_resized(self, img_file, scale = 2):
        img = load_img_resized(img_file, scale)
        reconstructed_img = self.upscale_net(img)
        return reconstructed_img

def pytensor2pil(img):
    img = torch.clamp(img, 0, 1) * 255
    img = img.data.cpu().numpy().transpose(0, 2, 3, 1)
    img = np.uint8(img)
    img = img[0, ...].squeeze()
    img = Image.fromarray(img)
    return img

def load_car_model(model_fn = "./models/2x/usn.pth", SCALE = 2):
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    model = EDSR(32, 256, scale=SCALE) #.cuda()
    model = nn.DataParallel(model, [0])
    model.load_state_dict(torch.load(model_fn,map_location=device))
    model = model.to(device)
    model.eval()
    torch.set_grad_enabled(False)
    return model

def load_car_kgn(model_fn = "./models/2x/kgn.pth", SCALE = 2, KSIZE = 7):
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    model = DSN(k_size=KSIZE, scale=SCALE) #.cuda(gpu)
    model = nn.DataParallel(model, [0])
    model.load_state_dict(torch.load(model_fn, map_location=device))
    model.eval()
    model = model.to(device)
    return model

def load_car_downsampler(model_fn = "./models/2x/dsn.pth", SCALE = 2, KSIZE = 7):
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    model = Downsampler(SCALE, KSIZE) #.cuda(gpu)
    model = nn.DataParallel(model, [0])
    model.load_state_dict(torch.load(model_fn, map_location=device))
    model.eval()
    model = model.to(device)
    return model

def load_img_resized(img_file, scale = 2):
    img = Image.open(img_file).convert('RGB')
    width, height = img.size
    pscale = float(1.0 / float(scale))
    img = resize_pil_img(img, int(pscale*width), int(pscale*height))
    img = np.array(img)
    h, w, _ = img.shape
    #img = img[:h // 8 * 8, :w // 8 * 8, :]
    img = np.array(img) / 255.
    img = img.transpose((2, 0, 1))
    img = torch.from_numpy(img).float().unsqueeze(0).cuda()
    return img

def load_img(img_file):
    img = Image.open(img_file).convert('RGB')
    img = np.array(img)
    h, w, _ = img.shape
    img = img[:h // 8 * 8, :w // 8 * 8, :]
    img = np.array(img) / 255.
    img = img.transpose((2, 0, 1))
    img = torch.from_numpy(img).float().unsqueeze(0).cuda()
    return img

def resize_pil_img(img, target_width, target_height):
    return img.resize((target_width,target_height), Image.ANTIALIAS)
def resize_torch_img(img, target_width, target_height):
    n_channels = img.shape[2]
    return torch.nn.functional.interpolate(img, size=(target_height, target_width, n_channels), mode='bicubic')