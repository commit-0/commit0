python examples/star/star.py \
  --model_name_or_path meta-llama/Llama-3.1-8B-Instruct \
  --dataset_name commit0/mbpp \
  -n 10 \
  --output_dir outputs \
  --low_cpu_mem_usage \
  --with_tracking \
  --report_to wandb \
  --iteration 5 \
  --learning_rate 1e-6 \
  --per_device_train_batch_size 1 \
  --gradient_accumulation_steps 8

