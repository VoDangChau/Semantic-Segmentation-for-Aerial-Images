# dataset settings
dataset_type = 'AgricultureVisionDataset'
data_root = 'Agriculture-Vision-2021'
img_norm_cfg = dict(mean=[123.675, 116.28, 103.53, 123.675], std=[58.395, 57.12, 57.375, 58.395], to_rgb=True)
crop_size = (512, 512)
num_channels = 4
train_pipeline = [
    dict(type='LoadImageFromFile', include_nir=True),
    dict(type='LoadAnnotations'),
    dict(type='Resize', img_scale=(1024, 512), ratio_range=(1.0, 2.0)),
    dict(type='RandomCrop', crop_size=crop_size, cat_max_ratio=0.75),
    dict(type='RandomFlip', prob=0.5),
    # dict(type='PhotoMetricDistortion',
    #      brightness_delta=18,
    #      contrast_range=(0.9, 1.2),
    #      saturation_range=(0.8, 1.2),
    #      hue_delta=10),
    dict(type='Normalize', **img_norm_cfg),
    dict(type='Pad', size=crop_size, pad_val=0, seg_pad_val=255),
    dict(type='DefaultFormatBundle'),
    dict(type='Collect', keys=['img', 'gt_semantic_seg']),
]
test_pipeline = [
    dict(type='LoadImageFromFile', include_nir=True),
    dict(
        type='MultiScaleFlipAug',
        img_scale=(512, 512),
        flip=False,
        transforms=[
            dict(type='Resize', keep_ratio=True),
            dict(type='RandomFlip'),
            dict(type='Normalize', **img_norm_cfg),
            dict(type='ImageToTensor', keys=['img']),
            dict(type='Collect', keys=['img']),
        ])
]
data = dict(samples_per_gpu=2,
            workers_per_gpu=2,
            train=dict(type=dataset_type,
                       data_root=data_root,
                       img_dir='train/images/rgb',
                       nir_dir='train/images/nir',
                       ann_dir='train/gt',
                       pipeline=train_pipeline),
            val=dict(type=dataset_type,
                     data_root=data_root,
                     img_dir='val/images/rgb',
                     nir_dir='val/images/nir',
                     ann_dir='val/gt',
                     pipeline=test_pipeline),
            test=dict(type=dataset_type,
                      data_root=data_root,
                      img_dir='val/images/rgb',
                      nir_dir='val/images/nir',
                      ann_dir='val/gt',
                      pipeline=test_pipeline))
