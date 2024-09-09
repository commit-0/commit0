import argparse
import difflib
import os
import shutil
from datasets import load_dataset, Dataset
from git import Repo
from openai import OpenAI
client = OpenAI()

def query_chat(text, model, temperature=1, top_p=1):
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": text}],
        temperature=temperature,
        top_p=top_p,
        response_format={
          "type": "text"
        }
    )
    return response.choices[0].message.content.strip()

def serialize_files(directory):
    out = dict()
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            splitted = file_path.split('/')
            hidden = False
            for one in splitted:
                if one.startswith('.'):
                    hidden = True
                    break
            if hidden:
                continue
            try:
                rel_path = os.path.relpath(file_path, directory)
                with open(file_path, 'r') as f:
                    curr = f"[start of {rel_path}]\n"
                    for i, line in enumerate(f, start=1):
                        curr += line
                    curr += f"[end of {rel_path}]"
                    out[rel_path] = curr
            except Exception as e:
                print(f"Could not read file {rel_path}: {e}")
    return out

def get_prompt(spec, code):
    prompt = f"You will be provided with a specification, and your task is to produce a repository based on the specification. You will complete this task with a sequence of steps. In each step, you will complete a (perhaps empty) code file. Make sure you read the specification carefully. <spec> {spec} </spec> <code> {code} </code> I need you to complete the provided code file. Your output should be the completed code file and in the following format: <code> [...your_completed_code...] </code>"
    return prompt

def process_output(text):
    text = text.strip()
    if text.startswith("<code>"):
        text = text[6:].strip()
    if text.endswith("</code>"):
        text = text[:-7].strip()
    if text.startswith("```"):
        text = text[3:].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    if text.startswith("python"):
        text = text[6:].strip()
    return text

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", type=str, required=True, help="The name of the model to use.")
    parser.add_argument("--dataset_name", type=str, required=True, help="The name of the dataset to use (via the datasets library).")
    parser.add_argument("--dataset_config_name", type=str, default=None, help="The configuration name of the dataset to use (via the datasets library).")
    parser.add_argument("--dataset_split", type=str, default=None, help="Which split of the dataset to load.")
    args = parser.parse_args()

    if args.dataset_name.endswith('json'):
        ds = load_dataset('json', data_files=args.dataset_name, split="train")
    else:
        ds = load_dataset(args.dataset_name, args.dataset_config_name, split=args.dataset_split)
    results = []
    for example in ds:
        # TODO: load from specific commit instead of main
        repo_url = example["repository"]
        repo_dir = repo_url.split('/')[-1]
        if repo_dir.endswith('.git'):
            repo_dir = repo_dir[:-len('.git')]
        Repo.clone_from(repo_url, repo_dir)
        files = serialize_files(repo_dir)
        example["full_output"] = dict()
        for f in example['files_to_edit']:
            prompt = get_prompt(example['specification'], files[f])
            response = query_chat(prompt, args.model_name, temperature=0.2)
            example["full_output"][f] = response
        diffs = []
        for f in example["full_output"]:
            with open(os.path.join(repo_dir, f), 'r') as fin:
                before = fin.readlines()
            after = process_output(example["full_output"][f]).splitlines(keepends=True)
            diff = difflib.unified_diff(
                before,
                after,
                fromfile='a/'+f,
                tofile='b/'+f,
            )
            diffs.append(''.join(diff))
        diffs = '\n'.join(diffs)
        example['model_patch'] = diffs
        shutil.rmtree(repo_dir)
        results.append(example)
    results = Dataset.from_list(results)
    results.to_json(args.dataset_name.replace('.json', f'-{args.model_name}_results.json'))

if __name__ == '__main__':
    main()
