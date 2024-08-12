#python -m swebench.harness.run_evaluation \
python run.py \
    --dataset_name spec2repo/spec2repo \
    --split test \
    --max_workers 2 \
    --predictions_path 'gold' \
    --instance_ids spec2repo__tinydb-01 \
    --run_id validate-gold \
    --spec_config configs/specs.yml \
    --req_config configs/reqs.yml
