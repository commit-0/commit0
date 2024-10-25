def run_team_for_repo(
    repo_base_dir: str,
    agent_config: AgentConfig,
    example: RepoInstance,
    update_queue: multiprocessing.Queue,
    branch: str,
    override_previous_changes: bool = False,
    backend: str = "modal",
    log_dir: str = str(RUN_AGENT_LOG_DIR.resolve()),
) -> None:
    """Run Aider for a given repository."""
    # get repo info
    _, repo_name = example["repo"].split("/")

    # before starting, display all information to terminal
    original_repo_name = repo_name
    update_queue.put(("start_repo", (original_repo_name, 0)))

    # repo_name = repo_name.lower()
    # repo_name = repo_name.replace(".", "-")

    repo_path = os.path.join(repo_base_dir, repo_name)
    repo_path = os.path.abspath(repo_path)

    try:
        local_repo = Repo(repo_path)
    except Exception:
        raise Exception(
            f"{repo_path} is not a git repo. Check if base_dir is correctly specified."
        )

    manager = AiderAgents(1, agent_config.model_name)
    coder = AiderAgents(agent_config.max_iteration, agent_config.model_name)
    

    # # if branch_name is not provided, create a new branch name based on agent_config
    # if branch is None:
    #     branch = args2string(agent_config)
    create_branch(local_repo, branch, example["base_commit"])

    # in cases where the latest commit of branch is not commit 0
    # set it back to commit 0
    latest_commit = local_repo.commit(branch)
    if latest_commit.hexsha != example["base_commit"] and override_previous_changes:
        local_repo.git.reset("--hard", example["base_commit"])

    target_edit_files, import_dependencies = get_target_edit_files(
        local_repo,
        example["src_dir"],
        example["test"]["test_dir"],
        str(latest_commit),
        example["reference_commit"],
    )


    # Call the commit0 get-tests command to retrieve test files
    test_files_str = get_tests(repo_name, verbose=0)
    test_files = sorted(list(set([i.split(":")[0] for i in test_files_str])))

    # prepare the log dir
    experiment_log_dir = (
        Path(log_dir)
        / repo_name
        / branch
        / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    )
    experiment_log_dir.mkdir(parents=True, exist_ok=True)

    # write agent_config to .agent.yaml in the log_dir for record
    agent_config_log_file = experiment_log_dir / ".agent.yaml"
    with open(agent_config_log_file, "w") as agent_config_file:
        yaml.dump(agent_config, agent_config_file)

    # TODO: make this path more general
    commit0_dot_file_path = str(Path(repo_path).parent.parent / ".commit0.yaml")
    manager_message = "Write a concise plan of attack to implement the entire repo, but don't actually do any coding. The plan should not include any reccommendations to add files and should be a maximum of 500 words."
    
    with DirContext(repo_path):
        if agent_config is None:
            raise ValueError("Invalid input")
        else:
            # when unit test feedback is not available, iterate over target files to edit

            update_queue.put(
                ("start_repo", (original_repo_name, len(target_edit_files)))
            )
            
            for f in target_edit_files:
                update_queue.put(("set_current_file", (repo_name, f)))
                dependencies = import_dependencies[f]
            file_name = "all"
            file_log_dir = experiment_log_dir / file_name
            lint_cmd = get_lint_cmd(repo_name, agent_config.use_lint_info)
                
            
            agent_return = manager.run(manager_message, "", lint_cmd, target_edit_files, file_log_dir)
            with open(agent_return.log_file, 'r', encoding='utf-8') as file:
                plan = file.read()
            coder_message = "follow this implementation plan: "+plan

            agent_return = coder.run(coder_message, "", lint_cmd, target_edit_files, file_log_dir)
            
            # for f in target_edit_files:
            #     update_queue.put(("set_current_file", (repo_name, f)))
            #     dependencies = import_dependencies[f]
            #     message = update_message_with_dependencies(coder_message, dependencies)
            #     file_name = f.replace(".py", "").replace("/", "__")
            #     file_log_dir = experiment_log_dir / file_name
            #     lint_cmd = get_lint_cmd(repo_name, agent_config.use_lint_info)
            #     agent_return = coder.run(message, "", lint_cmd, [f], file_log_dir)
            #     update_queue.put(
            #         (
            #             "update_money_display",
            #             (repo_name, file_name, agent_return.last_cost),
            #         )
            #     )
            update_queue.put(
                    (
                        "update_money_display",
                        (repo_name, file_name, agent_return.last_cost),
                    )
                )
    
    
    
    update_queue.put(("finish_repo", original_repo_name))

