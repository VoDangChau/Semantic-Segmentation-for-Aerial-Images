# Copyright (c) OpenMMLab. All rights reserved.
import warnings

from mmcv.cnn import MODELS as MMCV_MODELS
from mmcv.cnn.bricks.registry import ATTENTION as MMCV_ATTENTION
from mmcv.utils import Registry

MODELS = Registry('models', parent=MMCV_MODELS)
ATTENTION = Registry('attention', parent=MMCV_ATTENTION)

BACKBONES = MODELS
NECKS = MODELS
HEADS = MODELS
LOSSES = MODELS
SEGMENTORS = MODELS


def build_backbone(cfg):
    """Build backbone."""
    return BACKBONES.build(cfg)


def build_neck(cfg):
    """Build neck."""
    return NECKS.build(cfg)


def build_head(cfg):
    """Build head."""
    return HEADS.build(cfg)


def build_loss(cfg):
    """Build loss."""
    return LOSSES.build(cfg)


def build_train_model(cfg, train_cfg=None, test_cfg=None):
    """Build model."""
    if train_cfg is not None or test_cfg is not None:
        warnings.warn('train_cfg and test_cfg is deprecated, '
                      'please specify them in model', UserWarning)
    assert cfg.model.get('train_cfg') is None or train_cfg is None, \
        'train_cfg specified in both outer field and model field '
    assert cfg.model.get('test_cfg') is None or test_cfg is None, \
        'test_cfg specified in both outer field and model field '
    if 'custom' in cfg:
        cfg.custom['model_config'] = cfg.model
        cfg.custom['max_iters'] = cfg.runner.max_iters
        cfg.custom['resume_iters'] = getattr(cfg, "resume_iters", 0)
        cfg.custom["num_channels"] = cfg.num_channels
        cfg.custom["work_dir"] = cfg.work_dir
        return SEGMENTORS.build(cfg.custom, default_args=dict(train_cfg=train_cfg, test_cfg=test_cfg))
    else:
        return SEGMENTORS.build(cfg.model, default_args=dict(train_cfg=train_cfg, test_cfg=test_cfg))


def build_segmentor(cfg, train_cfg=None, test_cfg=None):
    """Build segmentor."""
    if train_cfg is not None or test_cfg is not None:
        warnings.warn('train_cfg and test_cfg is deprecated, '
                      'please specify them in model', UserWarning)
    assert cfg.get('train_cfg') is None or train_cfg is None, \
        'train_cfg specified in both outer field and model field '
    assert cfg.get('test_cfg') is None or test_cfg is None, \
        'test_cfg specified in both outer field and model field '
    if 'custom' in cfg:
        cfg.custom['model_config'] = cfg.model
        cfg.custom['max_iters'] = cfg.runner.max_iters
        cfg.custom['resume_iters'] = getattr(cfg, "resume_iters", 0)
        cfg.custom["num_channels"] = cfg.num_channels
        cfg.custom["work_dir"] = cfg.work_dir
        return SEGMENTORS.build(cfg.custom, default_args=dict(train_cfg=train_cfg, test_cfg=test_cfg))
    return SEGMENTORS.build(cfg, default_args=dict(train_cfg=train_cfg, test_cfg=test_cfg))