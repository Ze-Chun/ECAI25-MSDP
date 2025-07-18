from collections import defaultdict
import json
import argparse
import os
import random

import torch
from PIL import Image
from tqdm import tqdm

from interpreter import *
from executor import *
from methods import *

METHODS_MAP = {
    "baseline": Baseline,
    "random": Random,
    "parse": Parse,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_file", type=str, help="input file with expressions and annotations in jsonlines format")
    parser.add_argument("--image_root", type=str, help="path to images (train2014 directory of COCO)")
    parser.add_argument("--clip_model", type=str, default="RN50x16,ViT-B/32", help="which clip model to use (should use RN50x4, ViT-B/32, or both separated by a comma")
    parser.add_argument("--albef_path", type=str, default=None, help="to use ALBEF (instead of CLIP), specify the path to the ALBEF checkpoint")
    parser.add_argument("--method", type=str, default="parse", help="method to solve expressions")
    parser.add_argument("--box_representation_method", type=str, default="crop,blur", help="method of representing boxes as individual images (crop, blur, or both separated by a comma)")
    parser.add_argument("--box_method_aggregator", type=str, default="sum", help="method of combining box representation scores")
    parser.add_argument("--box_area_threshold", type=float, default=0.0, help="minimum area (as a proportion of image area) for a box to be considered as the answer")
    parser.add_argument("--output_file", type=str, default=None, help="(optional) output path to save results")
    parser.add_argument("--results_path", type=str, default='./output', help="(optional) output path to save results")
    parser.add_argument("--detector_file", type=str, default=None, help="(optional) file containing object detections. if not provided, the gold object boxes will be used.")
    parser.add_argument("--mock", action="store_true", help="(optional) mock CLIP execution.")
    parser.add_argument("--device", type=int, default=1, help="CUDA device to use.")
    parser.add_argument("--shuffle_words", action="store_true", help="If true, shuffle words in the sentence")
    parser.add_argument("--gradcam_alpha", type=float, nargs='+', help="alpha value to use for gradcam method")
    parser.add_argument("--enlarge_boxes", type=float, default=0.0, help="(optional) whether to enlarge boxes when passing them to the model")
    parser.add_argument("--part", type=str, default=None, help="(optional) specify how many parts to divide the dataset into and which part to run in the format NUM_PARTS,PART_NUM")
    parser.add_argument("--batch_size", type=int, default=1, help="number of instances to process in one model call (only supported for baseline model)")
    parser.add_argument("--baseline_head", action="store_true", help="For baseline, controls whether model is called on both full expression and head noun chunk of expression")
    parser.add_argument("--mdetr", type=str, default=None, help="to use MDETR as the executor model, specify the name of the MDETR model")
    parser.add_argument("--albef_block_num", type=int, default=8, help="block num for ALBEF gradcam")
    parser.add_argument("--albef_mode", type=str, choices=["itm", "itc"], default="itm")
    parser.add_argument("--expand_position_embedding",action="store_true")
    parser.add_argument("--gradcam_background", action="store_true")
    parser.add_argument("--mdetr_given_bboxes", action="store_true")
    parser.add_argument("--mdetr_use_token_mapping", action="store_true")
    parser.add_argument("--non_square_size", action="store_true")
    parser.add_argument("--gradcam_ensemble_before", action="store_true", help="Average gradcam maps of different models before summing over the maps")
    parser.add_argument("--cache_path", type=str, default=None, help="cache features")
    
    # Arguments related to Parse method.
    # control the pp
    parser.add_argument("--no_rel", action="store_true", help="Disable relation extraction.")
    parser.add_argument("--no_sup", action="store_true", help="Disable superlative extraction.")
    
    parser.add_argument("--no_null", action="store_true", help="Disable null keyword heuristics.")
    parser.add_argument("--ternary", action="store_true", help="Disable ternary relation extraction.")
    parser.add_argument("--baseline_threshold", type=float, default=float("inf"), help="(Parse) Threshold to use relations/superlatives.")
    parser.add_argument("--temperature", type=float, default=1., help="(Parse) Sigmoid temperature.")
    parser.add_argument("--superlative_head_only", action="store_true", help="(Parse) Superlatives only quanntify head predicate.")
    parser.add_argument("--sigmoid", action="store_true", help="(Parse) Use sigmoid, not softmax.")
    parser.add_argument("--no_possessive", action="store_true", help="(Parse) Model extraneous relations as possessive relations.")
    parser.add_argument("--expand_chunks", action="store_true", help="(Parse) Expand noun chunks to include descendant tokens that aren't ancestors of tokens in other chunks")
    parser.add_argument("--parse_no_branch", action="store_true", help="(Parse) Only do the parsing procedure if some relation/superlative keyword is in the expression")
    parser.add_argument("--possessive_no_expand", action="store_true", help="(Parse) Expand ent2 in possessive case")

    # common args
    parser.add_argument('--note', type=str, default='',
                        help='note of the experiment.')
    parser.add_argument('--visual_prompt', nargs='+', default='circle',
                        choices=['crop', 'cpt', 'cpt_seg', 'ov_seg', 'blur_seg',
                                 'keypoint',
                                 'box', 'box_mask', 'blur_box_mask', 'reverse_box_mask', 'grayscale_box_mask',
                                 'circle', 'circle_mask', 'blur_circle_mask', 'reverse_circle_mask', 'grayscale_circle_mask',
                                 'contour', 'mask', 'blur_mask', 'reverse_mask', 'grayscale_mask'],
                        help='visual prompt that will be marked on image')
    parser.add_argument('--expand_ratio', type=float, default=0.01,
                        help='ratio to expand around the boxes')
    parser.add_argument('--grounding', action='store_true', default=False,
                        help='If true, set metrics of REC and grounding tasks.')
    parser.add_argument('--recompute_box', action='store_true', default=False,
                        help='If true, the box will be recomputed according to mask.')
    parser.add_argument('--color_line', type=str, default='red',
                        help='color of the box, circle, and contour')
    parser.add_argument('--color_mask', type=str, default='green',
                        help='color of the mask')
    
    # line thickness
    parser.add_argument('--thickness', type=int, default=2,
                        help='thickness of the box, circle')
    parser.add_argument('--c_thickness', type=int, default=2,
                        help='thickness of the contour')
    # mask thickness
    parser.add_argument('--alpha', type=float, default=0.5,
                        help='alpha of the mask')
    parser.add_argument("--blur_std_dev", type=int, default=100, 
                        help="standard deviation of Gaussian blur")
    parser.add_argument("--contour_scale", type=float, default=1.0, 
                        help="resize ratio for the contour mask")
    # text prompt
    parser.add_argument('--text_prompt', type=str, default='a photo of <caption>',
                        help='text prompt')
    parser.add_argument('--score_subtracting', action='store_true', default=False,
                        help='If true, post proocess with score_subtracting.')
    
    # text denoising
    parser.add_argument('--TD', action='store_true', default=False,
                        help='If true, post proocess with text denoising.')

    
    parser.add_argument('--clip_image_size', type=int, default=336,
                        help='input image size of clip')
    parser.add_argument('--clip_processing', default='center_crop',
                        choices=['center_crop', 'padding', 'bias_crop', 'resize'],
                        help='preprocessing operation to the clip input images one of (center_crop, padding)')
    parser.add_argument('--clip_crop_pct', type=float, default=1.0,
                        help='Only use it when clip_processing is center_crop.')

    # sam args
    parser.add_argument('--sam_model', metavar='NAME', default='vit_h',
                        help='model architecture (default: vit_h)')
    parser.add_argument('--sam_pretrained', metavar='NAME', default='',
                        help='path to model checkpoints')
    parser.add_argument('--sam_image_size', type=int, default=1024,
                        help='input image size of sam')
    parser.add_argument('--min_mask_region_area', default=400, type=int,
                        help='If >0, postprocessing will be applied to remove disconnected regions and holes in masks.')
    parser.add_argument('--sam_multimask_output', action='store_true', default=False,
                        help='If true, the model will return three masks.')
    parser.add_argument('--sam_neg_label', action='store_true', default=False,
                        help='If true, the model will also take negative points as inputs.')
    parser.add_argument('--sam_prompt', nargs='+', default='box',
                        choices=['none', 'grid', 'box', 'keypoint'],
                        help='prompt that sam used to produce masks')

    args = parser.parse_args()
    os.makedirs(os.path.dirname(args.results_path), exist_ok=True)

    with open(args.input_file) as f:
        lines = f.readlines()
        data = [json.loads(line) for line in lines]

    device = f"cuda:{args.device}" if torch.cuda.is_available() and args.device >= 0 else "cpu"
    gradcam = args.method == "gradcam"
    if args.clip_model == 'FLAVA':
        executor = FLAVAExecutor(args, box_representation_method=args.box_representation_method, method_aggregator=args.box_method_aggregator, device=device, expand_position_embedding=args.expand_position_embedding, blur_std_dev=args.blur_std_dev, cache_path=args.cache_path)
    elif args.albef_path is not None:
        if args.method.split("_")[0] == "gradcam":
            if len(args.method.split("_")) == 1:
                args.method = "baseline"
            else:
                args.method = args.method.split("_")[1]
            gradcam_alpha = args.gradcam_alpha[0]
            executor = AlbefGradcamExecutor(args, config_path=os.path.join(args.albef_path, "config.yaml"), checkpoint_path=os.path.join(args.albef_path, "checkpoint.pth"), box_representation_method=args.box_representation_method, device=device, gradcam_alpha=gradcam_alpha, gradcam_mode=args.albef_mode, block_num=args.albef_block_num)
        else:
            executor = AlbefExecutor(args, config_path=os.path.join(args.albef_path, "config.yaml"), checkpoint_path=os.path.join(args.albef_path, "checkpoint.pth"), box_representation_method=args.box_representation_method, method_aggregator=args.box_method_aggregator, device=device, mode=args.albef_mode, blur_std_dev=args.blur_std_dev, cache_path=args.cache_path)
    elif args.mock:
        executor = MockExecutor()
    elif args.mdetr is not None:
        executor = MdetrExecutor(args, model_name=args.mdetr, device=device, use_token_mapping=args.mdetr_use_token_mapping, freeform_bboxes=not args.mdetr_given_bboxes)
    else:
        if args.method.split("_")[0] == "gradcam":
            if len(args.method.split("_")) == 1:
                args.method = "baseline"
            else:
                args.method = args.method.split("_")[1]
            executor = ClipGradcamExecutor(args, clip_model=args.clip_model, box_representation_method=args.box_representation_method, device=device, gradcam_alpha=args.gradcam_alpha, expand_position_embedding=args.expand_position_embedding, square_size=not args.non_square_size, background_subtract=args.gradcam_background, gradcam_ensemble_before=args.gradcam_ensemble_before)
        else:
            executor = ClipExecutor(args, clip_model=args.clip_model, box_representation_method=args.box_representation_method, method_aggregator=args.box_method_aggregator, device=device, square_size=not args.non_square_size, expand_position_embedding=args.expand_position_embedding, blur_std_dev=args.blur_std_dev, cache_path=args.cache_path)

    method = METHODS_MAP[args.method](args)
    correct_count = 0
    total_count = 0
    if args.output_file:
        output_file = open(args.output_file, "w")
    if args.detector_file:
        detector_file = open(args.detector_file)
        detections_list = json.load(detector_file)
        if isinstance(detections_list, dict):
            detections_map = {int(image_id): detections_list[image_id] for image_id in detections_list}
        else:
            detections_map = defaultdict(list)
            for detection in detections_list:
                detections_map[detection["image_id"]].append(detection["box"])
    if args.part is not None:
        num_parts = int(args.part.split(",")[0])
        part = int(args.part.split(",")[1])
        data = data[int(len(data)*part/num_parts):int(len(data)*(part+1)/num_parts)]
    batch_count = 0
    batch_boxes = []
    batch_gold_boxes = []
    batch_gold_index = []
    batch_file_names = []
    batch_sentences = []
    caption_bank = []
    for datum in data:
        if args.text_prompt == 'a photo of <caption>':
            caption = [f'a photo of {sentence["raw"].lower()}' for sentence in datum["sentences"]]
        elif args.text_prompt == 'This is <caption>':
            caption = [f'This is {sentence["raw"].lower()}' for sentence in datum["sentences"]]
        else:
            raise NotImplementedError
        caption_bank += caption
    print(caption_bank[:5])
    for datum in tqdm(data, ncols=100):
        if "coco" in datum["file_name"].lower():
            file_name = "_".join(datum["file_name"].split("_")[:-1])+".jpg"
            # print(file_name)
            # input()
        else:
            file_name = datum["file_name"]
        img_path = os.path.join(args.image_root, file_name)
        img = Image.open(img_path).convert('RGB')
        gold_boxes = [Box(x=ann["bbox"][0], y=ann["bbox"][1], w=ann["bbox"][2], h=ann["bbox"][3]) for ann in datum["anns"]]
        if isinstance(datum["ann_id"], int) or isinstance(datum["ann_id"], str):
            datum["ann_id"] = [datum["ann_id"]]
        assert isinstance(datum["ann_id"], list)
        gold_index = [i for i in range(len(datum["anns"])) if datum["anns"][i]["id"] in datum["ann_id"]]
        for sentence in datum["sentences"]:

            if args.detector_file:
                boxes = [Box(x=box[0], y=box[1], w=box[2], h=box[3]) for box in detections_map[int(datum["image_id"])]]
                if len(boxes) == 0:
                    boxes = [Box(x=0, y=0, w=img.width, h=img.height)]
            else:
                boxes = gold_boxes
            env = Environment(img, boxes, executor, (args.mdetr is not None and not args.mdetr_given_bboxes), str(datum["image_id"]))
            if args.shuffle_words:
                words = sentence["raw"].lower().split()
                random.shuffle(words)
                result = method.execute(" ".join(words), env)
            elif args.score_subtracting:
                sampled_caption_bank = np.random.choice(caption_bank, 500, replace=False).tolist()
                result = method.execute(sentence["raw"].lower(), env, sampled_caption_bank)
            else:
                result = method.execute(sentence["raw"].lower(), env)
            boxes = env.boxes
            # print(sentence["raw"].lower())
            correct = False
            # 算框的相似度
            for g_index in gold_index:
                if iou(boxes[result["pred"]], gold_boxes[g_index]) > 0.5:
                    correct = True
                    break
            if correct:
                result["correct"] = 1
                correct_count += 1
            else:
                result["correct"] = 0
            if args.detector_file:
                argmax_ious = []
                max_ious = []
                for g_index in gold_index:
                    ious = [iou(box, gold_boxes[g_index]) for box in boxes]
                    argmax_iou = -1
                    max_iou = 0
                    if max(ious) >= 0.5:
                        for index, value in enumerate(ious):
                            if value > max_iou:
                                max_iou = value
                                argmax_iou = index
                    argmax_ious.append(argmax_iou)
                    max_ious.append(max_iou)
                argmax_iou = -1
                max_iou = 0
                if max(max_ious) >= 0.5:
                    for index, value in zip(argmax_ious, max_ious):
                        if value > max_iou:
                            max_iou = value
                            argmax_iou = index
                result["gold_index"] = argmax_iou
            else:
                result["gold_index"] = gold_index
            result["bboxes"] = [[box.left, box.top, box.right, box.bottom] for box in boxes]
            result["file_name"] = file_name
            result["probabilities"] = result["probs"]
            result["text"] = sentence["raw"].lower()
            if args.output_file:
                # Serialize numpy arrays for JSON.
                for key in result:
                    if isinstance(result[key], np.ndarray):
                        result[key] = result[key].tolist()
                    if isinstance(result[key], np.int64):
                        result[key] = result[key].item()
                output_file.write(json.dumps(result)+"\n")
            total_count += 1
            # print(f"count:{correct_count}")
            # print(f"est_acc: {100 * correct_count / total_count:.3f}")

    if args.output_file:
        output_file.close()
    print(f"acc: {100 * correct_count / total_count:.3f}")
    stats = method.get_stats()
    res = {}
    res['acc'] = round(100 * correct_count / total_count, 3)
    if stats:
        pairs = sorted(list(stats.items()), key=lambda tup: tup[0])
        for key, value in pairs:
            if isinstance(value, float):
                print(f"{key}: {value:.5f}")
                res[key] = round(value, 5)
            else:
                print(f"{key}: {value}")
                res[key] = value

    with open(args.results_path, 'w') as f:
        json.dump(res, f, indent=4)

    print('accomplished!')
    sys.exit(f"{100 * correct_count / total_count}")