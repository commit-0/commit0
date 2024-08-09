python -m swebench.harness.run_evaluation \
    --dataset_name spec2repo \
    --split test \
    --max_workers 2 \
    --predictions_path $1 \
    --instance_ids spec2repo__minitorch-01 \
    --run_id validate-model-output
