import affine
import cv2
import cPickle as pickle
import numpy as np
import dorsal_utils
import imutils


def preprocess_images(fpath, imsize, output_targets):
    resz_target = output_targets[fpath]['resized']
    trns_target = output_targets[fpath]['transform']

    img = cv2.imread(fpath)
    resz, M = imutils.center_pad_with_transform(img, imsize)
    _, resz_buf = cv2.imencode('.png', resz)

    with resz_target.open('wb') as f1,\
            trns_target.open('wb') as f2:
        f1.write(resz_buf)
        pickle.dump(M, f2, pickle.HIGHEST_PROTOCOL)


# input1_targets: localization_targets
# input2_targets: segmentation_targets
def find_keypoints(fpath, input1_targets, input2_targets, output_targets):
    coords_target = output_targets[fpath]['keypoints-coords']
    visual_target = output_targets[fpath]['keypoints-visual']

    loc_fpath = input1_targets[fpath]['localization'].path
    loc = cv2.imread(loc_fpath)

    seg_fpath = input2_targets[fpath]['segmentation-data'].path
    with open(seg_fpath, 'rb') as f:
        seg = pickle.load(f)

    start, end = dorsal_utils.find_keypoints(seg[:, :, 0])

    # TODO: what to write for failed extractions?
    if start is not None:
        cv2.circle(loc, tuple(start[::-1]), 3, (255, 0, 0), -1)
    if end is not None:
        cv2.circle(loc, tuple(end[::-1]), 3, (0, 0, 255), -1)
    _, visual_buf = cv2.imencode('.png', loc)
    with coords_target.open('wb') as f1,\
            visual_target.open('wb') as f2:
        pickle.dump((start, end), f1, pickle.HIGHEST_PROTOCOL)
        f2.write(visual_buf)


# input1_targets: localization_targets
# input2_targets: segmentation_targets
# input3_targets: keypoints_targets
def extract_outline(fpath, scale,
                    input1_targets, input2_targets, input3_targets,
                    output_targets):
    coords_target = output_targets[fpath]['outline-coords']
    visual_target = output_targets[fpath]['outline-visual']

    loc_fpath = input1_targets[fpath]['localization-full'].path
    loc = cv2.imread(loc_fpath)

    seg_fpath = input2_targets[fpath]['segmentation-full-data']
    key_fpath = input3_targets[fpath]['keypoints-coords']
    with seg_fpath.open('rb') as f1,\
            key_fpath.open('rb') as f2:
        segm = pickle.load(f1)
        (start, end) = pickle.load(f2)

    if start is not None and end is not None:
        Mscale = affine.build_scale_matrix(scale)
        points_orig = np.vstack((start, end))[:, ::-1]  # ij -> xy
        points_refn = affine.transform_points(Mscale, points_orig)

        start_refn, end_refn = np.floor(points_refn[:, ::-1]).astype(np.int32)
        outline = dorsal_utils.extract_outline(loc, segm, start_refn, end_refn)
    else:
        outline = np.array([])

    # TODO: what to write for failed extractions?
    if outline.shape[0] > 0:
        loc[outline[:, 0], outline[:, 1]] = (255, 0, 0)

    _, visual_buf = cv2.imencode('.png', loc)
    with coords_target.open('wb') as f1,\
            visual_target.open('wb') as f2:
        pickle.dump(outline, f1, pickle.HIGHEST_PROTOCOL)
        f2.write(visual_buf)


#input_targets: extract_high_resolution_outline_targets
def compute_block_curvature(fpath, scales, oriented,
                            input_targets, output_targets):
    outline_coords_target = input_targets[fpath]['outline-coords']
    with open(outline_coords_target.path, 'rb') as f:
        outline = pickle.load(f)

    # no successful outline could be found
    if outline.shape[0] > 0:
        outline = outline[:, ::-1]
        idx = dorsal_utils.separate_leading_trailing_edges(outline)
        if idx is not None:
            te = outline[idx:]
            if oriented:
                curv = dorsal_utils.oriented_curvature(te, scales)
            else:
                curv = dorsal_utils.block_curvature(te, scales)
        else:
            curv = None
    else:
        curv = None

    curv_target = output_targets[fpath]['curvature']
    # write the failures too or it seems like the task did not complete
    with curv_target.open('wb') as f1:
        pickle.dump(curv, f1, pickle.HIGHEST_PROTOCOL)
