python -m swebench.harness.run_evaluation \
    --dataset_name spec2repo/spec2repo \
    --split test \
    --max_workers 2 \
    --predictions_path 'gold' \
    --instance_ids spec2repo__minitorch-01 \
    --run_id validate-gold
