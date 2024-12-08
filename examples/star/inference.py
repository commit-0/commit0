from typing import List
from datasets import Dataset
from vllm import LLM, SamplingParams

def generate_predictions(
    model_name: str,
    dataset: Dataset,
    temperature: float = 1.0,
    n: int = 1
) -> List[List[str]]:
    """
    Generate predictions for a given dataset using a specified language model and
    sampling parameters. The function loads the dataset, constructs prompts from
    each example, and obtains generated predictions. The resulting predictions are
    then added as a new column to the dataset.

    Args:
        model_name (str): Name of the model to use for generation.
        dataset (Dataset): The Dataset object.
        temperature (float, optional): Temperature setting for the model's
            sampling strategy. Default is 1.0.
        n (int, optional): Number of sampling runs per prompt. Default is 1.

    Returns:
        predictions (List[List[str]]): Predictions on the dataset.
    """
    sampling_params = SamplingParams(n=n, temperature=temperature, max_tokens=512)
    llm = LLM(model=model_name)

    prompts: List[str] = []
    for example in dataset:
        prompt = example["prompt"]
        test = example["test"]
        prompt = f"""Write a Python function implementation for the following prompt:

{prompt}

Your code should satisfy these tests:

{test}

Return only the implementation code, no tests or explanations. Be sure to include the relevant import statements:
```python
code
```
"""
        prompts.append(prompt)

    outputs = llm.generate(prompts, sampling_params)

    results: List[List[str]] = []
    for output in outputs:
        generated_texts = [one.text for one in output.outputs]
        results.append(generated_texts)
    return results
    #out_name = dataset_name.split("/")[-1]
    #out_name = f"wentingzhao/{out_name}_predictions_{n}"
    #ds.push_to_hub(out_name)
