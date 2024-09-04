import argparse
from pathlib import Path

import docker
import traceback
from datasets import load_dataset

from commit0.harness.constants import (
    APPLY_PATCH_FAIL,
    APPLY_PATCH_PASS,
    REPO_IMAGE_BUILD_DIR,
    RUN_EVALUATION_LOG_DIR,
)
from commit0.harness.docker_utils import (
    copy_to_container,
    exec_run_with_timeout,
    cleanup_container,
)
from commit0.harness.docker_build import (
    BuildImageError,
    build_container,
    close_logger,
    setup_logger,
)
from commit0.harness.spec import make_spec


class EvaluationError(Exception):
    def __init__(self, repo, message, logger):
        super().__init__(message)
        self.super_str = super().__str__()
        self.repo = repo
        self.log_file = logger.log_file
        self.logger = logger

    def __str__(self):
        return (
            f"Evaluation error for {self.repo}: {self.super_str}\n"
            f"Check ({self.log_file}) for more information."
        )

def main(hf_name: str, run_id: str, timeout: int):
    dataset = load_dataset(hf_name, split="test")
    for example in dataset:
        spec = make_spec(example)
        client = docker.from_env()

        # Set up logging directory
        repo = spec.repo.split('/')[-1]
        log_dir = RUN_EVALUATION_LOG_DIR / run_id / repo
        log_dir.mkdir(parents=True, exist_ok=True)

        # Link the image build dir in the log dir
        build_dir = REPO_IMAGE_BUILD_DIR / spec.repo_image_key.replace(":", "__")
        image_build_link = log_dir / "image_build_dir"
        if not image_build_link.exists():
            try:
                # link the image build dir in the log dir
                image_build_link.symlink_to(build_dir.absolute(), target_is_directory=True)
            except:
                # some error, idk why
                pass
        log_file = log_dir / "run_repo.log"
        logger = setup_logger(repo, log_file)

        # Run the repo
        container = None
        try:
            # Build + start repo container (repo image should already be built)
            container = build_container(spec, client, run_id, logger, nocache=True, force_rebuild=False)
            container.start()
            logger.info(f"Container for {repo} started: {container.id}")

            # Copy model prediction as patch file to container
            patch_file = Path(log_dir / "patch.diff")
            patch_file.write_text(example["patch"] or "")
            logger.info(
                f"Intermediate patch for {repo} written to {patch_file}, now applying to container..."
            )
            copy_to_container(container, patch_file, Path("/tmp/patch.diff"))

            # Attempt to apply patch to container
            val = container.exec_run(
                "git apply --allow-empty -v /tmp/patch.diff",
                workdir="/testbed",
                user="root",
            )
            if val.exit_code != 0:
                logger.info(f"Failed to apply patch to container, trying again...")
                
                # try "patch --batch --fuzz=5 -p1 -i {patch_path}" to try again
                val = container.exec_run(
                    "patch --batch --fuzz=5 -p1 -i /tmp/patch.diff",
                    workdir="/testbed",
                    user="root",
                )
                if val.exit_code != 0:
                    logger.info(f"{APPLY_PATCH_FAIL}:\n{val.output.decode('utf-8')}")
                    raise EvaluationError(
                        repo,
                        f"{APPLY_PATCH_FAIL}:\n{val.output.decode('utf-8')}",
                        logger,
                    )
                else:
                    logger.info(f"{APPLY_PATCH_PASS}:\n{val.output.decode('utf-8')}")
            else:
                logger.info(f"{APPLY_PATCH_PASS}:\n{val.output.decode('utf-8')}")

            # Get git diff before running eval script
            git_diff_output_before = (
                container.exec_run("git diff", workdir="/testbed").output.decode("utf-8").strip()
            )
            logger.info(f"Git diff before:\n{git_diff_output_before}")

            eval_file = Path(log_dir / "eval.sh")
            eval_file.write_text(spec.eval_script)
            logger.info(
                f"Eval script for {repo} written to {eval_file}; copying to container..."
            )
            copy_to_container(container, eval_file, Path("/eval.sh"))

            # Run eval script, write output to logs
            test_output, timed_out, total_runtime = exec_run_with_timeout(container, "/bin/bash /eval.sh", timeout)
            test_output_path = log_dir / "test_output.txt"
            logger.info(f'Test runtime: {total_runtime:_.2f} seconds')
            with open(test_output_path, "w") as f:
                f.write(test_output)
                logger.info(f"Test output for {repo} written to {test_output_path}")
                if timed_out:
                    f.write(f"\n\nTimeout error: {timeout} seconds exceeded.")
                    raise EvaluationError(
                        repo,
                        f"Test timed out after {timeout} seconds.",
                        logger,
                    )

            # Get git diff after running eval script
            git_diff_output_after = (
                container.exec_run("git diff", workdir="/testbed").output.decode("utf-8").strip()
            )

            # Check if git diff changed after running eval script
            logger.info(f"Git diff after:\n{git_diff_output_after}")
            if git_diff_output_after != git_diff_output_before:
                logger.info(f"Git diff changed after running eval script")

        except EvaluationError as e:
            error_msg = traceback.format_exc()
            logger.info(error_msg)
            print(e)
        except BuildImageError as e:
            error_msg = traceback.format_exc()
            logger.info(error_msg)
            print(e)
        except Exception as e:
            error_msg = (f"Error in evaluating model for {repo}: {e}\n"
                         f"{traceback.format_exc()}\n"
                         f"Check ({logger.log_file}) for more information.")
            logger.error(error_msg)
        finally:
            # Remove repo container + image, close logger
            cleanup_container(client, container, logger)
            close_logger(logger)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hf_name", type=str, help="HF dataset name")
    parser.add_argument("--run_id", type=str, help="Run id")
    parser.add_argument(
        "--timeout", type=int, default=1_800, help="Timeout (in seconds) for running tests for each instance"
        )
    args = parser.parse_args()
    main(**vars(args))
