from datasets import Dataset

submissions = {
    "org_name": ["test-save-commit0", "commit0-lite-with-test", "commit0-lite-plain", "commit0-all-plain", "openhands-commit0", "sweagent-commit0"],
    "branch": ["baseline", "fillin", "fillin", "fillin", "openhands", "sweagent", "openhands", "sweagent"],
    "display_name": ["Claude Sonnet 3.5 - Base", "Claude Sonnet 3.5 - Fill-in + Unit Test Feedback", "Claude Sonnet 3.5 - Fill-in", "Claude Sonnet 3.5 - Fill-in", "OpenHands", "SWE-Agent"], 
    "submission_date": ["09/25/2024", "09/25/2024", "09/25/2024", "09/25/2024", "11/25/2024", "11/26/2024"],
    "split": ["lite", "lite", "lite", "all", "all", "all", "lite", "lite"],
    "project_page": ["https://github.com/test-save-commit0", "https://github.com/commit0-lite-with-test", "https://github.com/commit0-lite-plain", "https://github.com/commit0-all-plain", "https://github.com/openhands-commit0", "https://github.com/sweagent-commit0"]
}

Dataset.from_dict(submissions).push_to_hub("celinelee/commit0_submissions")
