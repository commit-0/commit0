from datasets import Dataset

submissions = {
    "org_name": [
        "test-save-commit0",
        "commit0-fillin",
        "commit0-lite-test",
        "openhands-commit0",
        "sweagent-commit0",
    ],
    "branch": ["baseline", "sonnet", "sonnet", "openhands", "sweagent"],
    "display_name": [
        "Claude Sonnet 3.5 - Base",
        "Claude Sonnet 3.5 - Fill-in",
        "Claude Sonnet 3.5 - Fill-in + Lint & Unit Test Feedback",
        "OpenHands",
        "SWE-Agent",
    ],
    "submission_date": [
        "09/25/2024",
        "09/25/2024",
        "09/25/2024",
        "11/25/2024",
        "11/26/2024",
    ],
    "split": ["lite", "all", "lite", "all", "lite"],
    "project_page": [
        "https://github.com/test-save-commit0",
        "https://github.com/commit0-fillin",
        "https://github.com/commit0-lite-test",
        "https://github.com/openhands-commit0",
        "https://github.com/sweagent-commit0",
    ],
}

Dataset.from_dict(submissions).push_to_hub("celinelee/commit0_submissions")
