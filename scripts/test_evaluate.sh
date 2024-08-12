python run.py \
    --dataset_name wentingzhao/spec2repo \
    --split train \
    --max_workers 2 \
    --predictions_path 'gold' \
    --instance_ids spec2repo__tinydb-01 \
    --run_id validate-gold \
    --spec_config configs/specs.yml
