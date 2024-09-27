from datasets import Dataset

submissions = {
    "org_name": ["test-save-commit0", "commit0-lite-with-test", "commit0-lite-plain", "commit0-all-plain"],
    "branch": ["baseline", "fillin", "fillin", "fillin"],
    "display_name": ["Claude Sonnet 3.5 - Base", "Claude Sonnet 3.5 - Fill-in + Unit Test Feedback", "Claude Sonnet 3.5 - Fill-in", "Claude Sonnet 3.5 - Fill-in"],
    "submission_date": ["09/25/2024", "09/25/2024", "09/25/2024", "09/25/2024"],
    "split": ["lite", "lite", "lite", "all"],
    "project_page": ["https://github.com/test-save-commit0", "https://github.com/commit0-lite-with-test", "https://github.com/commit0-lite-plain", "https://github.com/commit0-all-plain"]
}

Dataset.from_dict(submissions).push_to_hub("celinelee/commit0_submissions")