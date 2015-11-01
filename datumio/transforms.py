# -*- coding: utf-8 -*-
"""
Container of augmentation procedures. 

TODO:
    - Check out why build center_uncenter needs a swap of row/col
    - See why we can't just use skimage affine, but need to do center/uncenter thing
    - Test numpy's random
    
"""
import skimage.transform
import numpy as np

#==============================================================================
# transform image
#==============================================================================
def fast_warp(img, tf, output_shape = None, mode='constant', order=1):
    """
    This wrapper function is faster than skimage.transform.warp
    
    Parameters
    ---------
    img: ndarray
        Input image to be transformed
    
    tf: skimage.transform._geometric.SimilarityTransform
        A built skimage.transform.SimilarityTransform, containing all the affine
        transformations to be applied to `img`.
    
    output_shape: tuple or list of len(2) of ints, optional
        Center-crop :math:`tf(img)` to dimensions of `output_shape`.
        If None (default), output_shape = (`img.shape[0]`, `img.shape[1]`)
    
    mode: str, optional
        Points outside the boundaries of the input are filled according to the 
        given mode (‘constant’, ‘nearest’, ‘reflect’ or ‘wrap’).
    
    order: int, optional
        The order of interpolation. The order has to be in the range 0-5:
         - 0: Nearest-neighbor
         - 1: Bi-linear (default)
         - 2: Bi-quadratic
         - 3: Bi-cubic
         - 4: Bi-quartic
         - 5: Bi-quintic
         
    Returns
    ---------
    warped: ndarray
        Transformed img with size given by `output_shape` 
        (or img.shape if `output_shape` = None).
    """
    m = tf.params # tf._matrix is deprecated. m is a 3x3 matrix
    if len(img.shape) < 3: # if image is greyscale
        img_wf = skimage.transform._warps_cy._warp_fast(img, m, output_shape=output_shape, mode=mode, order=order)
    else: # if image is not greyscale, e.g. RGB, RGBA, etc.
        nChannels = img.shape[-1]
        img_wf = np.empty((output_shape[0], output_shape[1], nChannels), dtype='float32') # (height, width, channels)
        for k in xrange(nChannels):
            img_wf[..., k] = skimage.transform._warps_cy._warp_fast(img[..., k], m, output_shape=output_shape, mode=mode)

    return img_wf

#==============================================================================
#  affine transformations
#==============================================================================
def build_centering_transform(image_shape, target_shape):
    """
    Builds a transform that shifts the center of the `image_shape` to 
    center of `target_shape`.
    
    Parameters
    ---------
    image_shape: tuple or list of len(2) of ints
        Input image shape to be re-centered
        
    target_shape: tuple or list of len(2) of ints
        Input image is recentered to the center of `target_shape`
    
    Returns
    ---------
    tf: skimage.transform._geometric.SimilarityTransform
        Built affine transformation.
    """
    rows, cols = image_shape
    trows, tcols = target_shape
    shift_x = (cols - tcols) / 2.0
    shift_y = (rows - trows) / 2.0
    return skimage.transform.SimilarityTransform(translation=(shift_x, shift_y))    

def build_center_uncenter_transforms(image_shape):
    """
    These are used to ensure that zooming and rotation happens around the center of the image.
    Use this transform to center and uncenter the image around such a transform.
    
    Parameters
    ---------
    image_shape: tuple or list of len(2) of ints
        Input image shape of (row, col)
    
    Returns
    ---------
    tf: skimage.transform._geometric.SimilarityTransform
        Built affine transformation.
    """
    center_shift = np.array([image_shape[1], image_shape[0]]) / 2.0 - 0.5 # need to swap rows and cols here apparently! confusing!
    tform_uncenter = skimage.transform.SimilarityTransform(translation=-center_shift)
    tform_center = skimage.transform.SimilarityTransform(translation=center_shift)
    return tform_center, tform_uncenter
    
def build_augmentation_transform(zoom=(1.0, 1.0), rotation=0., shear=0.,
                                 translation=(0, 0), flip_lr=False): 
    """
    Wrapper to build an affine transformation matrix applies: 
        zoom, rotate, shear, translate, and flip_lr, flip_ud
    
    See skimage.transform.AffineTransform for more details.
        
    Parameters
    ---------
    zoom: tuple or list of len(2) of floats
        E.g: (zoom_row, zoom_col). Scale image rows by zoom_row and image cols 
        by zoom_col. Float of < 1 indicate zoom out, >1 indicate zoom in.
    
    rotation: float, optional
        Rotation angle in counter-clockwise direction as `degrees`.
        Note: Original skimage implementation requires rotation as radiances.
        
    shear: float, optional
        Shear angle in counter-clockwise direction as `degrees`.
        Note: Original skimage implementation requires rotation as radiances.

    translation: tuple or list of len(2) of ints
        Translates image in (, ).
    
    flip_lr: bool, optional
        Flip image left/right
        
    Returns
    ---------
    skimage.transform._geometric.SimilarityTransform
        Built affine transformation.
    tf: 
    """
    if flip_lr:
        shear += 180
        rotation += 180
        # shear by 180 degrees is equivalent to rotation by 180 degrees + flip.
        # So after that we rotate it another 180 degrees to get just the flip.
        
    tform_augment = skimage.transform.AffineTransform(scale=(1/zoom[0], 1/zoom[1]), rotation=np.deg2rad(rotation), shear=np.deg2rad(shear), translation=translation)
    return tform_augment

def random_perturbation_transform(zoom_range, rotation_range, shear_range,
                                  translation_range_col, translation_range_row, 
                                  do_flip_lr=True, allow_stretch=False, rng=np.random):
    """
    Randomly perturbs image using affine transformations: zoom, rotate, shear,
        translate, flip_lr, and stretch.
    
    Parameters
    ---------
    zoom_range: 
    
    Returns
    ---------
    
    """            
    shift_x = rng.uniform(*translation_range_col)
    shift_y = rng.uniform(*translation_range_row)
    translation = (shift_x, shift_y)

    rotation = rng.uniform(*rotation_range)
    shear = rng.uniform(*shear_range)

    if do_flip_lr:
        flip = (rng.randint(2) > 0) # flip half of the time
    else:
        flip = False

    # random zoom
    log_zoom_range = [np.log(z) for z in zoom_range]
    if isinstance(allow_stretch, float):
        log_stretch_range = [-np.log(allow_stretch), np.log(allow_stretch)]
        zoom = np.exp(rng.uniform(*log_zoom_range))
        stretch = np.exp(rng.uniform(*log_stretch_range))
        zoom_x = zoom * stretch
        zoom_y = zoom / stretch
    elif allow_stretch is True: # avoid bugs, f.e. when it is an integer
        zoom_x = np.exp(rng.uniform(*log_zoom_range))
        zoom_y = np.exp(rng.uniform(*log_zoom_range))
    else:
        zoom_x = zoom_y = np.exp(rng.uniform(*log_zoom_range))
    # the range should be multiplicatively symmetric, so [1/1.1, 1.1] instead of [0.9, 1.1] makes more sense.
        
    return build_augmentation_transform((zoom_x, zoom_y), rotation, shear, translation, flip)
        
        
def perturb(img, augmentation_params, target_shape=(50, 50), rng=np.random):
    """
    
    """
    # # DEBUG: draw a border to see where the image ends up
    # img[0, :] = 0.5
    # img[-1, :] = 0.5
    # img[:, 0] = 0.5
    # img[:, -1] = 0.5
    tform_centering = build_centering_transform(img.shape[:2], target_shape)
    tform_center, tform_uncenter = build_center_uncenter_transforms(img.shape[:2])
    tform_augment = random_perturbation_transform(rng=rng, **augmentation_params)
    tform_augment = tform_uncenter + tform_augment + tform_center # shift to center, augment, shift back (for the rotation/shearing)
    return fast_warp(img, tform_centering + tform_augment, output_shape=target_shape, mode='constant').astype('float32')