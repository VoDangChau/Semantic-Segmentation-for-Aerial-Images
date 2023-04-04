# Copyright (c) OpenMMLab. All rights reserved.
import argparse
import os
import os.path as osp
import shutil
import time
import warnings
from pathlib import Path

import mmcv
import torch
from mmcv.cnn.utils import revert_sync_batchnorm
from mmcv.parallel import MMDataParallel, MMDistributedDataParallel
from mmcv.runner import get_dist_info, init_dist, load_checkpoint, wrap_fp16_model
from mmcv.utils import DictAction

from mmseg import digit_version
from mmseg.apis import multi_gpu_test, single_gpu_test
from mmseg.datasets import build_dataloader, build_dataset
from mmseg.models import build_segmentor
from mmseg.utils import setup_multi_processes

custom_pipeline = [
    dict(type='LoadImageFromFile', include_nir=True),
    dict(type='LoadAnnotations'),
    dict(type='MultiScaleFlipAug',
         img_scale=(512, 512),
         flip=False,
         transforms=[
             dict(type='Resize', keep_ratio=True),
             dict(type='RandomFlip'),
             dict(type='Normalize',
                  mean=[123.675, 116.28, 103.53, 123.675],
                  std=[58.395, 57.12, 57.375, 58.395],
                  to_rgb=True),
             dict(type='ImageToTensor', keys=['img', 'gt_semantic_seg']),
             dict(type='Collect', keys=['img', 'gt_semantic_seg'])
         ])
]


def parse_args():
    parser = argparse.ArgumentParser(description='mmseg test (and eval) a model')
    parser.add_argument('config', help='test config file path')
    parser.add_argument('--checkpoint', required=False, help='checkpoint file, latest.pth if not specified')
    parser.add_argument('--work-dir',
                        help=('if specified, the evaluation metric results will be dumped'
                              'into the directory as json'))
    parser.add_argument('--aug-test', action='store_true', help='Use Flip and Multi scale aug')
    parser.add_argument('--out', help='output result file in pickle format')
    parser.add_argument('--format-only',
                        action='store_true',
                        help='Format the output results without perform evaluation. It is'
                        'useful when you want to format the result to a specific format and '
                        'submit it to the test server')
    parser.add_argument('--eval',
                        type=str,
                        nargs='+',
                        help='evaluation metrics, which depends on the dataset, e.g., "mIoU"'
                        ' for generic datasets, and "cityscapes" for Cityscapes')
    parser.add_argument('--show', action='store_true', help='show results')
    parser.add_argument('--show-all', action='store_true', help='show results')
    parser.add_argument('--show-labels', action='store_true', help='show results')

    parser.add_argument('--show-dir', help='directory where painted images will be saved')
    parser.add_argument('--gpu-collect', action='store_true', help='whether to use gpu to collect results.')
    parser.add_argument('--gpu-id',
                        type=int,
                        default=0,
                        help='id of gpu to use '
                        '(only applicable to non-distributed testing)')
    parser.add_argument('--tmpdir',
                        help='tmp directory used for collecting results from multiple '
                        'workers, available when gpu_collect is not specified')
    parser.add_argument('--options',
                        nargs='+',
                        action=DictAction,
                        help="--options is deprecated in favor of --cfg_options' and it will "
                        'not be supported in version v0.22.0. Override some settings in the '
                        'used config, the key-value pair in xxx=yyy format will be merged '
                        'into config file. If the value to be overwritten is a list, it '
                        'should be like key="[a,b]" or key=a,b It also allows nested '
                        'list/tuple values, e.g. key="[(a,b),(c,d)]" Note that the quotation '
                        'marks are necessary and that no white space is allowed.')
    parser.add_argument('--cfg-options',
                        nargs='+',
                        action=DictAction,
                        help='override some settings in the used config, the key-value pair '
                        'in xxx=yyy format will be merged into config file. If the value to '
                        'be overwritten is a list, it should be like key="[a,b]" or key=a,b '
                        'It also allows nested list/tuple values, e.g. key="[(a,b),(c,d)]" '
                        'Note that the quotation marks are necessary and that no white space '
                        'is allowed.')
    parser.add_argument('--eval-options', nargs='+', action=DictAction, help='custom options for evaluation')
    parser.add_argument('--launcher', choices=['none', 'pytorch', 'slurm', 'mpi'], default='none', help='job launcher')
    parser.add_argument('--channels', choices=['rgb', 'irrg'], default='rgb', help='channels to plot')
    parser.add_argument('--opacity',
                        type=float,
                        default=0.5,
                        help='Opacity of painted segmentation map. In (0, 1] range.')
    parser.add_argument('--local_rank', type=int, default=0)
    args = parser.parse_args([''])
    if 'LOCAL_RANK' not in os.environ:
        os.environ['LOCAL_RANK'] = str(args.local_rank)

    if args.options and args.cfg_options:
        raise ValueError('--options and --cfg-options cannot be both '
                         'specified, --options is deprecated in favor of --cfg-options. '
                         '--options will not be supported in version v0.22.0.')
    if args.options:
        warnings.warn('--options is deprecated in favor of --cfg-options. '
                      '--options will not be supported in version v0.22.0.')
        args.cfg_options = args.options

    return args


def main():
    args = parse_args()
    args.config = r'configs/aias/rgbir_aias_aug075_s0_alpha0968_gamma4.py'
    args.eval = 'mIoU'
    args.checkpoint = r'work_dirs/latest.pth'
    args.work_dir = r'work_dirs/segformer'
    assert args.out or args.eval or args.format_only or args.show \
        or args.show_dir, \
        ('Please specify at least one operation (save/eval/format/show the '
         'results / save the results) with the argument "--out", "--eval"'
         ', "--format-only", "--show" or "--show-dir"')

    if args.eval and args.format_only:
        raise ValueError('--eval and --format_only cannot be both specified')

    if args.out is not None and not args.out.endswith(('.pkl', '.pickle')):
        raise ValueError('The output file must be a pkl file.')

    cfg = mmcv.Config.fromfile(args.config)
    if args.cfg_options is not None:
        cfg.merge_from_dict(args.cfg_options)

    cfg.data.test.pipeline = custom_pipeline

    # set multi-process settings
    setup_multi_processes(cfg)

    # set cudnn_benchmark
    if cfg.get('cudnn_benchmark', False):
        torch.backends.cudnn.benchmark = True
    if args.aug_test:
        # hard code index
        cfg.data.test.pipeline[1].img_ratios = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75]
        cfg.data.test.pipeline[1].flip = True
    cfg.model.pretrained = None
    cfg.data.test.test_mode = True

    if args.gpu_id is not None:
        cfg.gpu_ids = [args.gpu_id]

    # init distributed env first, since logger depends on the dist info.
    if args.launcher == 'none':
        cfg.gpu_ids = [args.gpu_id]
        distributed = False
        if len(cfg.gpu_ids) > 1:
            warnings.warn(f'The gpu-ids is reset from {cfg.gpu_ids} to '
                          f'{cfg.gpu_ids[0:1]} to avoid potential error in '
                          'non-distribute testing time.')
            cfg.gpu_ids = cfg.gpu_ids[0:1]
    else:
        distributed = True
        init_dist(args.launcher, **cfg.dist_params)

    rank, _ = get_dist_info()
    # allows not to create
    cfg.work_dir = args.work_dir
    work_dir = cfg.work_dir
    if args.work_dir is not None and rank == 0:
        work_dir = args.work_dir
        mmcv.mkdir_or_exist(osp.abspath(args.work_dir))
        timestamp = time.strftime('%Y%m%d_%H%M%S', time.localtime())
        if args.aug_test:
            json_file = osp.join(args.work_dir, f'eval_multi_scale_{timestamp}.json')
        else:
            json_file = osp.join(args.work_dir, f'eval_single_scale_{timestamp}.json')
    elif rank == 0:
        mmcv.mkdir_or_exist(osp.abspath(work_dir))
        timestamp = time.strftime('%Y%m%d_%H%M%S', time.localtime())
        if args.aug_test:
            json_file = osp.join(work_dir, f'eval_multi_scale_{timestamp}.json')
        else:
            json_file = osp.join(work_dir, f'eval_single_scale_{timestamp}.json')

    # build the dataloader
    # TODO: support multiple images per gpu (only minor changes are needed)
    dataset = build_dataset(cfg.data.test)
    data_loader = build_dataloader(dataset,
                                   samples_per_gpu=1,
                                   workers_per_gpu=cfg.data.workers_per_gpu,
                                   dist=distributed,
                                   shuffle=False)

    # build the model and load checkpoint
    cfg.model.train_cfg = None
    model = build_segmentor(cfg, test_cfg=cfg.get('test_cfg'))
    model.adapt_input()
    fp16_cfg = cfg.get('fp16', None)
    if fp16_cfg is not None:
        wrap_fp16_model(model)

    if not args.checkpoint:
        args.checkpoint = str(Path(work_dir) / "latest.pth")
    checkpoint = load_checkpoint(model, args.checkpoint, map_location='cpu')
    if 'CLASSES' in checkpoint.get('meta', {}):
        model.CLASSES = checkpoint['meta']['CLASSES']
    else:
        print('"CLASSES" not found in meta, use dataset.CLASSES instead')
        model.CLASSES = dataset.CLASSES
    if 'PALETTE' in checkpoint.get('meta', {}):
        model.PALETTE = checkpoint['meta']['PALETTE']
    else:
        print('"PALETTE" not found in meta, use dataset.PALETTE instead')
        model.PALETTE = dataset.PALETTE

    # clean gpu memory when starting a new evaluation.
    torch.cuda.empty_cache()
    eval_kwargs = {} if args.eval_options is None else args.eval_options

    # Deprecated
    efficient_test = eval_kwargs.get('efficient_test', False)
    if efficient_test:
        warnings.warn('``efficient_test=True`` does not have effect in tools/test.py, '
                      'the evaluation and format results are CPU memory efficient by '
                      'default')

    eval_on_format_results = (args.eval is not None and 'cityscapes' in args.eval)
    if eval_on_format_results:
        assert len(args.eval) == 1, 'eval on format results is not ' \
                                    'applicable for metrics other than ' \
                                    'cityscapes'
    if args.format_only or eval_on_format_results:
        if 'imgfile_prefix' in eval_kwargs:
            tmpdir = eval_kwargs['imgfile_prefix']
        else:
            tmpdir = '.format_cityscapes'
            eval_kwargs.setdefault('imgfile_prefix', tmpdir)
        mmcv.mkdir_or_exist(tmpdir)
    else:
        tmpdir = None

    if not distributed:
        suffix = "mask" if args.opacity > 0 else args.channels
        show_dir = str(Path(work_dir) / f"preds_{suffix}") if args.show else None
        # when we want to plot all together
        if args.show_all:
            show_dir = str(Path(work_dir) / "preds")
        channels = [2, 1, 0] if args.channels == "rgb" else [3, 2, 1]

        warnings.warn('SyncBN is only supported with DDP. To be compatible with DP, '
                      'we convert SyncBN to BN. Please use dist_train.sh which can '
                      'avoid this error.')
        if not torch.cuda.is_available():
            assert digit_version(mmcv.__version__) >= digit_version('1.4.4'), \
                'Please use MMCV >= 1.4.4 for CPU training!'
        model = revert_sync_batchnorm(model)
        model = MMDataParallel(model, device_ids=cfg.gpu_ids)
        results = single_gpu_test(model,
                                  data_loader,
                                  show_dir,
                                  channels=channels,
                                  efficient_test=False,
                                  opacity=args.opacity,
                                  show_all=args.show_all,
                                  show_labels=args.show_labels,
                                  pre_eval=args.eval is not None and not eval_on_format_results,
                                  format_only=args.format_only or eval_on_format_results,
                                  format_args=eval_kwargs)
    else:
        model = MMDistributedDataParallel(model.cuda(),
                                          device_ids=[torch.cuda.current_device()],
                                          broadcast_buffers=False)
        results = multi_gpu_test(model,
                                 data_loader,
                                 args.tmpdir,
                                 args.gpu_collect,
                                 False,
                                 pre_eval=args.eval is not None and not eval_on_format_results,
                                 format_only=args.format_only or eval_on_format_results,
                                 format_args=eval_kwargs)

    rank, _ = get_dist_info()
    if rank == 0:
        if args.out:
            warnings.warn('The behavior of ``args.out`` has been changed since MMSeg '
                          'v0.16, the pickled outputs could be seg map as type of '
                          'np.array, pre-eval results or file paths for '
                          '``dataset.format_results()``.')
            print(f'\nwriting results to {args.out}')
            mmcv.dump(results, args.out)
        if args.eval:
            eval_kwargs.update(metric=args.eval)
            metric = dataset.evaluate(results, **eval_kwargs)
            metric_dict = dict(config=args.config, metric=metric)
            mmcv.dump(metric_dict, json_file, indent=4)
            if tmpdir is not None and eval_on_format_results:
                # remove tmp dir when cityscapes evaluation
                shutil.rmtree(tmpdir)


if __name__ == '__main__':
    main()