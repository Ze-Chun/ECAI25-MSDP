import os

dataset_list = [
    ['refcoco', 'unc', 'val'], ['refcoco', 'unc', 'testA'], ['refcoco', 'unc', 'testB']
]

experiment = 'MSDP'
clip_model = 'ViT-L/14@336px,RN50x16'
save_dir = f'./output/{clip_model.replace("/", "-")}/{experiment}'

for (dataset, split_by, split) in dataset_list:
    print(dataset, split_by, split)
    split = split.lower()
    cmd = f"python ./main.py \
        --input_file ./data/{dataset}_{split}.jsonl \
        --image_root ./data/train2014 \
        --method parse \
        --device 0 \
        --box_area_threshold 0.05 \
        --box_method_aggregator sum \
        --clip_model {clip_model} \
        --detector_file ./data/{dataset}_dets_dict.json \
        --box_representation_method crop,blur,fine-grained \
        --sam_model vit_h \
        --sam_pretrained ./sam/huge/sam_vit_h_4b8939.pth \
        --clip_image_size 384 \
        --clip_processing padding \
        --visual_prompt  circle blur_mask grayscale_mask contour \
        --sam_prompt box \
        --thickness 2 \
        --c_thickness 2 \
        --blur_std_dev 100 \
        --alpha 0.5 \
        --TD \
        --cache_path {save_dir}/cache/ \
        --results_path {save_dir}/{dataset}-{split}.json"

    print(cmd)
    os.system(cmd)
