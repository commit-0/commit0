from datasets import Dataset

submissions = {
    "branch": ["baseline"],
    "display_name": ["Claude Sonnet - Base"],
    "submission_date": ["09/25/2024"],
    "split": ["lite"],
    "project_page": ["https://commit-0.github.io"]
}

Dataset.from_dict(submissions).push_to_hub("celinelee/commit0_submissions")