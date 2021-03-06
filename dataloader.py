import cv2
import torch
import numpy as np
from torch.utils import data

from config import config
from utils.img_utils import random_scale, random_mirror, normalize, \
    generate_random_crop_pos, random_crop_pad_to_shape


class TrainPre(object):
    def __init__(self, img_mean, img_std):
        self.img_mean = img_mean
        self.img_std = img_std
        edge_radius = 7
        #maybe the hit or no hit
        self.edge_kernel = cv2.getStructuringElement(cv2.MORPH_RECT,
                                                     (edge_radius, edge_radius))

    def __call__(self, img, gt):
        #flip
        img, gt = random_mirror(img, gt)
        #according the paper
        if config.train_scale_array is not None:
            img, gt, scale = random_scale(img, gt, config.train_scale_array)

        id255 = np.where(gt == 255)
        no255_gt = np.array(gt)
        no255_gt[id255] = 0
        cgt = cv2.Canny(no255_gt, 5, 5, apertureSize=7)
        #get border imformation from canny
        cgt = cv2.dilate(cgt, self.edge_kernel)
        cgt[cgt == 255] = 1

        #img white
        img = normalize(img, self.img_mean, self.img_std)


        crop_size = (config.image_height, config.image_width)
        crop_pos = generate_random_crop_pos(img.shape[:2], crop_size)

        p_img, _ = random_crop_pad_to_shape(img, crop_pos, crop_size, 0)
        p_gt, _ = random_crop_pad_to_shape(gt, crop_pos, crop_size, 255)
        p_cgt, _ = random_crop_pad_to_shape(cgt, crop_pos, crop_size, 255)

        p_img = p_img.transpose(2, 0, 1)

        extra_dict = {'aux_label': p_cgt}

        return p_img, p_gt, extra_dict


def get_train_loader(engine, dataset):
    data_setting = {'img_root': config.img_root_folder,
                    'gt_root': config.gt_root_folder,
                    'train_source': config.train_source,
                    'eval_source': config.eval_source}


    train_preprocess = TrainPre(config.image_mean, config.image_std)
    train_dataset = dataset(data_setting, "train", train_preprocess,config.batch_size * config.niters_per_epoch)


    train_sampler = None
    is_shuffle = True
    batch_size = config.batch_size

    if engine.distributed:
        train_sampler = torch.utils.data.distributed.DistributedSampler(
            train_dataset)
        batch_size = config.batch_size // engine.world_size
        is_shuffle = False

    train_loader = data.DataLoader(train_dataset,
                                   batch_size=batch_size,
                                   num_workers=config.num_workers,
                                   drop_last=True,
                                   shuffle=is_shuffle,
                                   pin_memory=True,
                                   sampler=train_sampler)

    return train_loader, train_sampler
