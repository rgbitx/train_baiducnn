#!/usr/bin/env python
# coding: utf-8

"""
under development.
python 3.7.3
"""

import numpy as np
from nuscenes.nuscenes import NuScenes
from nuscenes.utils.data_classes import LidarPointCloud
import matplotlib.pyplot as plt
from typing import Tuple
import h5py
import feature_generator as fg


def view_points(points: np.ndarray,
                view: np.ndarray,
                normalize: bool) -> np.ndarray:

    assert view.shape[0] <= 4
    assert view.shape[1] <= 4
    assert points.shape[0] == 3

    viewpad = np.eye(4)
    viewpad[:view.shape[0], :view.shape[1]] = view

    nbr_points = points.shape[1]

    # Do operation in homogenous coordinates
    points = np.concatenate((points, np.ones((1, nbr_points))))
    points = np.dot(viewpad, points)
    points = points[:3, :]
    if normalize:
        points = points / points[2:3, :].repeat(3, 0).reshape(3, nbr_points)

    return points


def get_color(category_name: str) -> Tuple[int, int, int]:
    """ Provides the default colors based on the category names. """
    if category_name in ['vehicle.bicycle', 'vehicle.motorcycle']:
        return 255, 61, 99  # Red
    elif 'vehicle' in category_name:
        return 255, 158, 0  # Orange
    elif 'human.pedestrian' in category_name:
        return 0, 0, 230  # Blue
    elif 'cone' in category_name or 'barrier' in category_name:
        return 0, 0, 0  # Black
    else:
        return 255, 0, 255  # Magenta


def points_in_box2d(box2d: np.ndarray, points: np.ndarray):
    p1 = box2d[0]
    p_x = box2d[1]
    p_y = box2d[3]

    i = p_x - p1
    j = p_y - p1
    v = points - p1

    iv = np.dot(i, v)
    jv = np.dot(j, v)

    mask_x = np.logical_and(0 <= iv, iv <= np.dot(i, i))
    mask_y = np.logical_and(0 <= jv, jv <= np.dot(j, j))
    mask = np.logical_and(mask_x, mask_y)

    return mask


grid_range = 60
size = 640
# size = 100
rows = 640
cols = 640

gsize = 2 * grid_range / size

# center -> x, y
# in_features = np.empty((0, size, size, 8), dtype=np.float32)
# out_features = np.empty((0, size, size, 1), dtype=np.float32)
# loss_weights = np.empty((0, size, size, 1), dtype=np.float16)

# in_features_val = np.empty((0, size, size, 8), dtype=np.float32)
# out_features_val = np.empty((0, size, size, 1), dtype=np.float32)
# loss_weights_val = np.empty((0, size, size, 1), dtype=np.float16)

in_features = []
out_features = []
loss_weights = []

in_features_val = []
out_features_val = []
loss_weights_val = []

channel = 5
# dataroot = '/home/kosuke/dataset/nuScenes/'
dataroot = "/media/kosuke/f798886c-8a70-48a4-9b66-8c9102072e3e/nuScenes/trainval"
# nusc_version = "v1.0-mini"
nusc_version = "v1.0-trainval"

nusc = NuScenes(
    version=nusc_version,
    dataroot=dataroot, verbose=True)
ref_chan = 'LIDAR_TOP'
data_id = 0

for my_scene in nusc.scene:
    first_sample_token = my_scene['first_sample_token']
    token = first_sample_token

    while(token != ''):
        print("--- {} ".format(data_id) + token + " ---")
        # out_feature = np.zeros((1, size, size, 1), dtype=np.float32)
        # loss_weight = np.full((1, size, size, 1), 0.5, dtype=np.float16)
        out_feature = np.zeros((size, size, 1), dtype=np.float16)
        loss_weight = np.full((size, size, 1), 0.5, dtype=np.float16)
        my_sample = nusc.get('sample', token)
        sd_record = nusc.get('sample_data', my_sample['data'][ref_chan])
        sample_rec = nusc.get('sample', sd_record['sample_token'])
        chan = sd_record['channel']

        pc, times = LidarPointCloud.from_file_multisweep(
            nusc, sample_rec, chan, ref_chan, nsweeps=10)
        _, boxes, _ = nusc.get_sample_data(sd_record['token'], box_vis_level=0)

        # not needed. This is equal to points = pc.points[:3, :]
        points = view_points(pc.points[:3, :], np.eye(4), normalize=False)
        dists = np.sqrt(np.sum(pc.points[:2, :] ** 2, axis=0))

        ticks = np.arange(-grid_range, grid_range + gsize, gsize)

        for box_idx, box in enumerate(boxes):
            # print("box_idx  {}/{}".format(box_idx, len(boxes)))
            view = np.eye(4)

            corners3d = view_points(box.corners(), view, normalize=False)
            height = np.linalg.norm(corners3d.T[0] - corners3d.T[3])

            # corners 2d
            corners = corners3d[:2, :]
            box2d = corners.T[[2, 3, 7, 6]]
            corners_height = corners3d[2, :]
            height = corners_height[0] - corners_height[2]

            # find search_area
            box2d_left = box2d[:, 0].min()
            box2d_right = box2d[:, 0].max()
            box2d_top = box2d[:, 1].max()
            box2d_bottom = box2d[:, 1].min()

            grid_centers = (ticks + gsize / 2)[:len(ticks) - 1]

            search_area_left_idx = np.abs(
                grid_centers - box2d_left).argmin() - 1
            search_area_right_idx = np.abs(
                grid_centers - box2d_right).argmin() + 1
            search_area_bottom_idx = np.abs(
                grid_centers - box2d_bottom).argmin() - 1
            search_area_top_idx = np.abs(
                grid_centers - box2d_top).argmin() + 1

            box2d_center = box2d.mean(axis=0)

            # start from lefght bottom, go right.
            for i in range(search_area_left_idx, search_area_right_idx):
                for j in range(search_area_bottom_idx, search_area_top_idx):
                    # grid_center is in meter coords
                    grid_center = np.array([grid_centers[i], grid_centers[j]])
                    if(points_in_box2d(box2d, grid_center)):
                        # out_feature[0, i, j, 0] = 1.
                        # loss_weight[0, i, j, 0] = 1.
                        out_feature[i, j, 0] = 1.
                        loss_weight[i, j, 0] = 1.

        # This is input feature
        feature_generator = fg.Feature_generator()
        feature_generator.generate(pc.points.T)
        in_feature = feature_generator.feature
        # for i in range(8):
        #     print("{}-----{}".format(i, np.count_nonzero(in_feature[:, i])))

        # check if input data is correct
        grid_centers = (ticks + gsize / 2)[:len(ticks) - 1]

        # pos_y, pos_x, 8

        in_feature = in_feature.reshape(size, size, 8)
        # in_feature = in_feature[np.newaxis, :, :, :]
        # in_feature = in_feature.astype(np.float32)
        out_feature = np.flip(np.flip(out_feature, axis=1), axis=2)
        # out_feature = out_feature.astype(np.float32)
        loss_weight = np.flip(np.flip(loss_weight, axis=1), axis=2)
        # loss_weight = loss_weight.astype(np.float16)

        if(data_id % 10):
            # in_features = np.append(in_features, in_feature, axis=0)
            # out_features = np.append(out_features, out_feature, axis=0)
            # loss_weights = np.append(loss_weights, loss_weight, axis=0)

            in_features.append(in_feature)
            out_features.append(out_feature)
            loss_weights.append(loss_weight)

            # print("out_feateres.shape" + str(out_features.shape))
            # print("in_feateres.shape" + str(in_features.shape))
            # print("loss_weights.shape" + str(loss_weights.shape))
            # print("out_feateres.dtype" + str(out_features.dtype))
            # print("in_feateres.dtype" + str(in_features.dtype))
            # print("loss_weights.dtype" + str(loss_weights.dtype))
        else:
            # in_features_val = np.append(in_features_val, in_feature, axis=0)
            # out_features_val = np.append(out_features_val, out_feature, axis=0)
            # loss_weights_val = np.append(loss_weights_val, loss_weight, axis=0)

            in_features_val.append(in_feature)
            out_features_val.append(out_feature)
            loss_weights_val.append(loss_weight)
            print("create val data")

        token = my_sample['next']
        data_id += 1
        if(data_id == 100):
            break
    if(data_id == 100):
        break

with h5py.File('100_nusc_baidu_confidence_val.h5', 'w') as f:
    # transform data into caffe format
    out_features_val = np.array(out_features_val)
    out_features_val = np.transpose(
        out_features_val, (0, 3, 2, 1))  # NxWxHxC -> NxCxHxW
    print(out_features_val.shape)
    f.create_dataset('output', dtype=np.float16, data=out_features_val)
    out_features_val = None

    loss_weights_val = np.array(loss_weights_val)
    loss_weights_val = np.transpose(
        loss_weights_val, (0, 3, 2, 1))  # NxWxHxC -> NxCxHxW
    print(loss_weights_val.shape)
    f.create_dataset('loss_weight', dtype=np.float16, data=loss_weights_val)
    loss_weights_val = None

    in_features_val = np.array(in_features_val)
    in_features_val = np.transpose(
        in_features_val, (0, 3, 2, 1))  # NxWxHxC -> NxCxHxW
    print(in_features_val.shape)
    f.create_dataset('data', dtype=np.float16, data=in_features_val)
    in_features_val = None

with h5py.File('100_nusc_baidu_confidence.h5', 'w') as f:
    # transform data into caffe format
    out_features = np.array(out_features)
    out_features = np.transpose(
        out_features, (0, 3, 2, 1))  # NxWxHxC -> NxCxHxW
    print(out_features.shape)
    f.create_dataset('output', dtype=np.float16, data=out_features)
    out_features = None

    loss_weights = np.array(loss_weights)
    loss_weights = np.transpose(
        loss_weights, (0, 3, 2, 1))  # NxWxHxC -> NxCxHxW
    print(loss_weights.shape)
    f.create_dataset('loss_weight', dtype=np.float16, data=loss_weights)
    loss_weight = None

    in_features = np.array(in_features)
    in_features = np.transpose(
        in_features, (0, 3, 2, 1))  # NxWxHxC -> NxCxHxW
    print(in_features.shape)
    f.create_dataset('data', dtype=np.float16, data=in_features)
    in_features = None
