import os
import tempfile
import sys
import json
import cv2
import piq
import torch
import yaml
# import kornia
import numpy as np
import PIL.Image as pil_image

from glob import glob
from typing import Any, Dict, Optional, List
from iq_tool_box.datasets import DSModifier
from iq_tool_box.metrics import Metric
from iq_tool_box.experiments import ExperimentInfo

from joblib import Parallel, delayed

import torch.backends.cudnn as cudnn

# MSRN
from msrn.msrn import load_msrn_model, process_file_msrn
    
# FSRCNN
from utils.utils_fsrcnn import convert_ycbcr_to_rgb, preprocess
from models.model_fsrcnn import FSRCNN

# LIIF
# from models.liif import models
# from models import models_liif
# from models_liif import modelsliif
# from config.config_srcnn import Config_srcnn
# from testing.test_fsrcnn import test_fsrcnn

class Args():
    def __init__(self):
        pass

class ModelConfS3Loader():
    
    def __init__(
        self,
        model_fn      = "single_frame_sr/SISR_MSRN_X2_BICUBIC.pth",
        config_fn_lst = [],
        bucket_name   = "image-quality-framework",
        algo          = "FSRCNN"
    ):
        
        self.fn_dict = {
            f"conf{enu}":fn
            for enu,fn in enumerate(config_fn_lst)
        }
        
        self.fn_dict["model"]   =  model_fn
        self.model_fn           =  model_fn
        self.config_fn_lst      =  config_fn_lst
        self.bucket_name        =  bucket_name
        self.algo               =  algo
        
    def load_ai_model_and_stuff(self) -> List[Any]:
        
        # Rename to full bucket subdirs...
        # First file is the model
        
        print( self.fn_dict["model"] )
        
        fn_lst = [
            os.path.join("iq-sisr-use-case/models/weights",self.fn_dict["model"])
        ] + [
            os.path.join("iq-sisr-use-case/models/config",fn)
            for fn in self.config_fn_lst
        ]
        
        with tempfile.TemporaryDirectory() as tmpdirname:
            
            print( self.fn_dict )
            
            for k in self.fn_dict:

                bucket_fn = self.fn_dict[k]

                local_fn = os.path.join(
                    tmpdirname , k
                )
                
                kind = ('weights' if k=='model' else 'config')
                
                url = f"https://{self.bucket_name}.s3-eu-west-1.amazonaws.com/iq-sisr-use-case/models/{kind}/{bucket_fn}"

                print( url , ' ' , local_fn )

                os.system( f"wget {url} -O {local_fn}" )

                if not os.path.exists( local_fn ):
                    print( 'AWS model file not found' )
                    raise

            if self.algo=='FSRCNN':

                args = self._load_args(os.path.join(
                    tmpdirname ,"conf0"
                ))
                model = self._load_model_fsrcnn(os.path.join(
                    tmpdirname ,"model"
                ), args )

            elif self.algo=='LIIF':
                
                args = self._load_args(os.path.join(
                    tmpdirname ,"conf0"
                ))
                model,loader = self._load_model_liif(os.path.join(
                    tmpdirname ,"model"
                ), args, os.path.join(
                    tmpdirname ,"conf1"
                ) )
                
            elif self.algo=='MSRN':
                
                args = None
                model = self._load_model_msrn(
                    os.path.join(tmpdirname ,"model")
                )
                
            else:
                print(f"Error: unknown algo: {self.algo}")
                raise

            return model , args
    
    def _load_args( self, config_fn: str ) -> Any:
        """Load Args"""

        args = Args()
        
        with open(config_fn) as jsonfile:
            args_dict = json.load(jsonfile)

        for k in args_dict:
            setattr( args, k, args_dict[k] )

        return args
    
    def _load_model_fsrcnn( self, model_fn: str,args: Any ) -> Any:
        """Load Model"""

        cudnn.benchmark = True
        device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
        
        model = FSRCNN(scale_factor=args.scale).to(device)

        state_dict = model.state_dict()
        for n, p in torch.load(model_fn, map_location=lambda storage, loc: storage).items():
            if n in state_dict.keys():
                state_dict[n].copy_(p)
            else:
                raise KeyError(n)

        model.eval()

        return model
    
    def _load_model_liif(self,model_fn: str,args: Any,yml_fn: str) -> Any:
        """Load Model"""

        os.environ['CUDA_VISIBLE_DEVICES'] = "0"
        
        with open(yml_fn, 'r') as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
        
        spec = config['test_dataset']
        # Save config and spec in self
        self.config = config
        self.spec = spec
        #dataset = datasets.make(spec['dataset'])
        #dataset = datasets.make(spec['wrapper'], args={'dataset': dataset})
        #loader = DataLoader(dataset, batch_size=spec['batch_size'],
        #                    num_workers=8, pin_memory=True)
        
        model_spec = torch.load(model_fn)['model']
        model = models_liif.make(model_spec, load_sd=True).cuda()
        
        model.eval()
        
        return model
    
    def _load_model_msrn(self,model_fn: str) -> Any:
        """Load MSRN Model"""
        return load_msrn_model(model_fn)

#########################
# Custom IQF
#########################

class DSModifierLIIF(DSModifier):
    """
    Class derived from DSModifier that modifies a dataset iterating its folder.

    Args:
        ds_modifer: DSModifier. Composed modifier child

    Attributes:
        name: str. Name of the modifier
        ds_modifer: DSModifier. Composed modifier child
        params: dict. Contains metainfomation of the modifier
    """
    def __init__(
        self,
        ds_modifier: Optional[DSModifier] = None,
        params: Dict[str, Any] = {
            "algo":"LIIF",
            "config": ["LIIF_config.json","test_liif.yaml"],
            "model": "liif_UCMerced/epoch-best.pth"
        },
    ):
        params['algo'] = 'LIIF'
        algo           = params['algo']
        
        subname = algo + '_' + os.path.splitext(params['config'][0])[0]+'_'+os.path.splitext(params['model'])[0].replace('/','-')
        self.name = f"sisr+{subname}"
        
        self.params: Dict[str, Any] = params
        self.ds_modifier = ds_modifier
        self.params.update({"modifier": "{}".format(self._get_name())})
        
        model_conf = ModelConfS3Loader(
                model_fn      = params['model'],
                config_fn_lst = params['config'],
                bucket_name   = "image-quality-framework",
                algo          = "LIIF"
        )
        
        model,args = model_conf.load_ai_model_and_stuff()
        
        self.spec   =  model_conf.spec
        self.args   =  args
        self.model  =  model
        
    def _ds_input_modification(self, data_input: str, mod_path: str) -> str:
        """Modify images
        Iterates the data_input path loading images, processing with _mod_img(), and saving to mod_path
        Args
            data_input: str. Path of the original folder containing images
            mod_path: str. Path to the new dataset
        Returns:
            Name of the new folder containign the images
        """
        input_name = os.path.basename(data_input)
        dst = os.path.join(mod_path, input_name)
        os.makedirs(dst, exist_ok=True)
        
        print(f'For each image file in <{data_input}>...')
        
        spec = self.spec
        dataset = datasets.make(spec['dataset'])
        dataset = datasets.make(spec['wrapper'], args={'dataset': dataset})
        loader = DataLoader(dataset, batch_size=spec['batch_size'],
                           num_workers=8, pin_memory=True)
        
        if data_norm is None:
            data_norm = {
                'inp': {'sub': [0], 'div': [1]},
                'gt': {'sub': [0], 'div': [1]}
            }
        t = data_norm['inp']
        inp_sub = torch.FloatTensor(t['sub']).view(1, -1, 1, 1).cuda()
        inp_div = torch.FloatTensor(t['div']).view(1, -1, 1, 1).cuda()
        t = data_norm['gt']
        gt_sub = torch.FloatTensor(t['sub']).view(1, 1, -1).cuda()
        gt_div = torch.FloatTensor(t['div']).view(1, 1, -1).cuda()

        if eval_type is None:
            metric_fn = utils.calc_psnr
        elif eval_type.startswith('div2k'):
            scale = int(eval_type.split('-')[1])
            metric_fn = partial(utils.calc_psnr, dataset='div2k', scale=scale)
        elif eval_type.startswith('benchmark'):
            scale = int(eval_type.split('-')[1])
            metric_fn = partial(utils.calc_psnr, dataset='benchmark', scale=scale)
        else:
            raise NotImplementedError

        val_res = utils.Averager()
        val_ssim = utils.Averager() #test

        pbar = tqdm(loader, leave=False, desc='val')
        count = 0
        for enu,batch in enumerate(pbar):
            
            try:
                imgp = self._mod_img( batch )
                cv2.imwrite( os.path.join(dst, f"{enu}"+'+'+self.params['algo']+'.png'), imgp )
            except Exception as e:
                print(e)
            
        return input_name

    def _mod_img(self, batch: Any) -> None:

        for k, v in batch.items():
            batch[k] = v.cuda()

        inp = (batch['inp'] - inp_sub) / inp_div
        if eval_bsize is None:
            with torch.no_grad():
                pred = self.model(inp, batch['coord'], batch['cell'])
        else:
            pred = batched_predict(self.model, inp,
                                   batch['coord'], batch['cell'], eval_bsize)
        pred = pred * gt_div + gt_sub
        pred.clamp_(0, 1)
        
        return pred.detach().cpu().numpy()

class DSModifierFSRCNN(DSModifier):
    """
    Class derived from DSModifier that modifies a dataset iterating its folder.

    Args:
        ds_modifer: DSModifier. Composed modifier child

    Attributes:
        name: str. Name of the modifier
        ds_modifer: DSModifier. Composed modifier child
        params: dict. Contains metainfomation of the modifier
    """
    def __init__(
        self,
        ds_modifier: Optional[DSModifier] = None,
        params: Dict[str, Any] = {
            "algo":"FSRCNN",
            "config": ["test.json"],
            "model": "FSRCNN_1to033_x3_noblur/best.pth"
        },
    ):
        
        params['algo'] = 'FSRCNN'
        algo           = params['algo']
        
        subname = algo + '_' + os.path.splitext(params['config'][0])[0]+'_'+os.path.splitext(params['model'])[0].replace('/','-')
        self.name = f"sisr+{subname}"
        
        self.params: Dict[str, Any] = params
        self.ds_modifier = ds_modifier
        self.params.update({"modifier": "{}".format(self._get_name())})

        model_conf = ModelConfS3Loader(
                model_fn      = params['model'],
                config_fn_lst = params['config'],
                bucket_name   = "image-quality-framework",
                algo          = "FSRCNN"
        )
        
        self.device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
        self.model, self.args = model_conf.load_ai_model_and_stuff()
        
    def _ds_input_modification(self, data_input: str, mod_path: str) -> str:
        """Modify images
        Iterates the data_input path loading images, processing with _mod_img(), and saving to mod_path

        Args
            data_input: str. Path of the original folder containing images
            mod_path: str. Path to the new dataset
        Returns:
            Name of the new folder containign the images
        """
        input_name = os.path.basename(data_input)
        dst = os.path.join(mod_path, input_name)
        os.makedirs(dst, exist_ok=True)
        
        print(f'For each image file in <{data_input}>...')
        
        for image_file in glob( os.path.join(data_input,'*.tif') ):

            try:
                imgp = self._mod_img( image_file )
                cv2.imwrite( os.path.join(dst, os.path.basename(image_file)+'+'+self.params['algo']+'.tif'), imgp )
            except Exception as e:
                print(e)
        
        print('Done.')
        
        return input_name

    def _mod_img(self, image_file: str) -> np.array:
        
        args = self.args
        model = self.model
        
        image = pil_image.open(image_file).convert('RGB')

        image_width = (image.width // args.scale) * args.scale
        image_height = (image.height // args.scale) * args.scale

        hr = image.resize((image_width, image_height), resample=pil_image.BICUBIC)
        lr = hr.resize((hr.width // args.scale, hr.height // args.scale), resample=pil_image.BICUBIC)
        bicubic = lr.resize((lr.width * args.scale, lr.height * args.scale), resample=pil_image.BICUBIC)

        lr, _ = preprocess(lr, self.device)
        _, ycbcr = preprocess(bicubic, self.device)

        with torch.no_grad():
            preds = model(lr).clamp(0.0, 1.0)

        preds = preds.mul(255.0).cpu().numpy().squeeze(0).squeeze(0)

        output = np.array([preds, ycbcr[..., 1], ycbcr[..., 2]]).transpose([1, 2, 0])
        output = np.clip(convert_ycbcr_to_rgb(output), 0.0, 255.0).astype(np.uint8)
        
        return output

class DSModifierMSRN(DSModifier):
    """
    Class derived from DSModifier that modifies a dataset iterating its folder.

    Args:
        ds_modifer: DSModifier. Composed modifier child

    Attributes:
        name: str. Name of the modifier
        ds_modifer: DSModifier. Composed modifier child
        params: dict. Contains metainfomation of the modifier
    """
    def __init__(
        self,
        ds_modifier: Optional[DSModifier] = None,
        params: Dict[str, Any] = {
            "algo":"MSRN",
            "zoom": 3,
            "config": [],
            "model": "MSRN/SISR_MSRN_X2_BICUBIC.pth"
        },
    ):
        
        params['algo'] = 'MSRN'
        algo           = params['algo']
        
        self.name = f"mfsr+{algo}_modifier"
        
        self.params: Dict[str, Any] = params
        self.ds_modifier = ds_modifier
        self.params.update({"modifier": "{}".format(self._get_name())})
        
        model_conf = ModelConfS3Loader(
                model_fn      = params['model'],
                config_fn_lst = [],
                bucket_name   = "image-quality-framework",
                algo          = "MSRN"
        )
        
        self.model,_ = model_conf.load_ai_model_and_stuff()
        
    def _ds_input_modification(self, data_input: str, mod_path: str) -> str:
        """Modify images
        Iterates the data_input path loading images, processing with _mod_img(), and saving to mod_path

        Args
            data_input: str. Path of the original folder containing images
            mod_path: str. Path to the new dataset
        Returns:
            Name of the new folder containign the images
        """
        input_name = os.path.basename(data_input)
        dst = os.path.join(mod_path, input_name)
        os.makedirs(dst, exist_ok=True)
        
        print(f'For each image file in <{data_input}>...')
        
        for image_file in glob( os.path.join(data_input,'*.tif') ):

            try:
                imgp = self._mod_img( image_file )
                cv2.imwrite( os.path.join(dst, os.path.basename(image_file)+'+'+self.params['algo']+'.tif'), imgp )
            except Exception as e:
                print(e)
        
        print('Done.')
        
        return input_name

    def _mod_img(self, image_file: str) -> np.array:
        
        zoom       = self.params["zoom"]
        loaded     = cv2.imread(image_file, -1)
        wind_size  = loaded.shape[1]
        gpu_device = "0"
        res_output = 1/zoom # inria resolution

        rec_img = process_file_msrn(
            loaded,
            self.model,
            compress=True,
            res_output=res_output,
            wind_size=wind_size+10, stride=wind_size+10,
            scale=2,
            batch_size=1,
            padding=5
        )
        
        return rec_img

#########################
# Similarity Metrics
#########################
    
class SimilarityMetrics( Metric ):
    
    def __init__( self, experiment_info: ExperimentInfo ) -> None:
        self.metric_names = ['ssim','psnr','gmsd','mdsi','haarpsi','fid']
        self.cut = cut
        self.experiment_info = experiment_info
        
    def apply(self, predictions: str, gt_path: str) -> Any:
        """
        In this case gt_path will be a glob criteria to the HR images
        """
        
        # These are actually attributes from ds_wrapper
        self.data_path = os.path.dirname(gt_path)
        
        # predictions be like /mlruns/1/6f1b6d86e42d402aa96665e63c44ef91/artifacts'
        guessed_run_id = predictions.split(os.sep)[-3]
        modifier_subfold = [
            k
            for k in self.experiment_info.runs
            if self.experiment_info.runs[k]['run_id']==guessed_run_id
        ][0]
        
        pred_fn_lst = glob(os.path.join( self.data_path,'test','*.tif' ))
        stats = { met:0.0 for met in self.metric_names }
        cut = self.cut
        
        fid = piq.FID()
        
        for pred_fn in pred_fn_lst:
            
            # pred_fn be like: xview_id1529imgset0012+hrn.png
            img_name = os.path.basename(pred_fn)
            gt_fn = os.path.join(self.data_path,"test",f"{img_name}")
            
            pred = cv2.imread( pred_fn )/255
            gt = cv2.imread( gt_fn )/255
            
            pred = torch.from_numpy( pred )
            gt = torch.from_numpy( gt )
            
            pred = pred.view(1,-1,pred.shape[-2],pred.shape[-1])
            gt = gt.view(1,-1,gt.shape[-2],gt.shape[-1])
            
            pred = torch.transpose( pred, 3, 1 )
            gt   = torch.transpose( gt  , 3, 1 )
            
            stats['ssim'] += piq.ssim(pred,gt).item()
            stats['psnr'] += piq.psnr(pred,gt).item()
            stats['gmsd'] += piq.gmsd(pred,gt).item()
            stats['mdsi'] += piq.mdsi(pred,gt).item()
            stats['haarpsi']+= piq.haarpsi(pred,gt).item()
            
            stats['fid'] += np.sum( [
                fid( torch.squeeze(pred)[i,...], torch.squeeze(gt)[i,...] ).item()
                for i in range( pred.shape[1] )
            ] ) / pred.shape[1]
            
        for k in stats:
            # If there are results for the given modifier...
            if len(pred_fn_lst)!=0:
                stats[k] = stats[k]/len(pred_fn_lst)
                
        return stats