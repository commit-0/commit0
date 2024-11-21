import time
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    ProgressColumn,
    Task,
)
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.columns import Columns
from rich.rule import Rule
from rich.align import Align
from collections import OrderedDict
from types import TracebackType
import json
from datetime import datetime


class RepoBox:
    def __init__(self, name: str, style: str):
        self.name = name
        self.style = style

    def __rich__(self):
        return Panel(
            Text(self.name, style=self.style), expand=False, border_style=self.style
        )


class RepoProgressColumn(ProgressColumn):
    """Custom progress column for displaying the progress of a repository."""

    def render(self, task: Task) -> Text:
        """Render the progress of a repository."""
        return Text(f"{int(task.completed or 0)}/{int(task.total or 1)}")


class RepoCountColumn(ProgressColumn):
    """Custom progress column for displaying the count of finished repositories."""

    def render(self, task: Task) -> Text:
        """Render the count of finished repositories."""
        return Text(f"{int(task.completed or 0)}/{int(task.total or 1)}")


class OngoingRepo:
    def __init__(
        self, name: str, current_file: str, finished_files: list[str], total_files: int
    ):
        self.name = name
        self.current_file = current_file
        self.finished_files = finished_files
        self.total_files = total_files

    def __rich__(self):
        progress = Progress(
            SpinnerColumn(),
            BarColumn(bar_width=None),
            RepoProgressColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        )
        _ = progress.add_task(
            "", total=self.total_files, completed=len(self.finished_files)
        )

        content = [
            Text("Current working file:", style="bold"),
            Text(self.current_file, style="green"),
            Rule(style="dim"),
            Text("Finished files (recent 5):", style="bold"),
        ] + [Text(file, style="dim green") for file in self.finished_files[-6:-1][::-1]]
        return Panel(
            Group(progress, *content),
            title=self.name,
            border_style="yellow",
            expand=True,
        )


class TerminalDisplay:
    def __init__(self, total_repos: int):
        self.console = Console()
        self.total_repos = total_repos
        self.not_started_repos = []
        self.finished_repos = []
        self.ongoing_repos = OrderedDict()
        self.finished_files = {}
        self.total_files_per_repo = {}
        self.repo_money_spent = {}
        self.display_repo_progress_num = 5
        self.start_time_per_repo = {}
        self.end_time_per_repo = {}
        self.total_time_spent = 0
        self.branch_name = ""

        self.overall_progress = Progress(
            SpinnerColumn(),
            BarColumn(bar_width=None),
            RepoCountColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        )
        self.overall_task = self.overall_progress.add_task(
            "[green]Processing", total=total_repos
        )

        self.layout = Layout()
        self.layout.split_column(
            Layout(name="progress", size=3),
            Layout(name="info", size=6),
            Layout(name="main", ratio=14),
        )
        self.layout["progress"].split_row(
            Layout(name="pbar", ratio=4),
            Layout(name="time", ratio=1),
            Layout(name="money", ratio=1),
        )

        self.layout["progress"]["pbar"].update(
            Panel(self.overall_progress, title="Overall Progress", border_style="blue")
        )
        self.time_display = Text("0s", justify="center")
        self.layout["progress"]["time"].update(
            Panel(self.time_display, title="Time Taken", border_style="blue")
        )
        self.money_display = Text("$0.00", justify="center")
        self.layout["progress"]["money"].update(
            Panel(self.money_display, title="$$$$", border_style="blue")
        )

        self.layout["info"].split_column(
            Layout(name="other_info", ratio=1),
            Layout(name="agent_info", ratio=1),
        )
        self.layout["info"]["other_info"].split_row(
            Layout(name="backend", ratio=1),
            Layout(name="branch", ratio=2),
            Layout(name="log_dir", ratio=2),
        )
        self.layout["info"]["agent_info"].split_row(
            Layout(name="agent_name", ratio=1),
            Layout(name="model_name", ratio=1),
            Layout(name="run_tests", ratio=1),
            Layout(name="use_topo_sort_dependencies", ratio=1),
            Layout(name="use_repo_info", ratio=1),
            Layout(name="use_unit_tests_info", ratio=1),
            Layout(name="use_spec_info", ratio=1),
            Layout(name="use_lint_info", ratio=1),
        )

        self.backend_display = Text("Using: ", justify="center")
        self.layout["info"]["other_info"]["backend"].update(
            Panel(self.backend_display, title="Backend", border_style="blue")
        )
        self.branch_display = Text("", justify="center")
        self.layout["info"]["other_info"]["branch"].update(
            Panel(self.branch_display, title="Branch", border_style="blue")
        )
        self.log_dir_display = Text("", justify="center")
        self.layout["info"]["other_info"]["log_dir"].update(
            Panel(self.log_dir_display, title="Log Directory", border_style="blue")
        )

        self.layout["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=2),
        )
        self.layout["main"]["left"].split_column(
            Layout(name="not_started", ratio=1),
            Layout(name="finished", ratio=1),
        )
        # Initialize panels with empty content
        self.layout["main"]["left"]["not_started"].update(
            Panel(Text(""), title="Not Started Repos", border_style="red")
        )
        self.layout["main"]["left"]["finished"].update(
            Panel(Text(""), title="Finished Repos", border_style="green")
        )

        self.layout["main"]["right"].update(
            Panel(Layout(name="ongoing"), title="Ongoing", border_style="yellow")
        )

    def update_repo_progress_num(self, display_repo_progress_num: int) -> None:
        """Update the number of repositories to display in the ongoing section."""
        self.display_repo_progress_num = display_repo_progress_num

    def update_agent_display(
        self,
        agent_name: str,
        model_name: str,
        run_tests: bool,
        use_topo_sort_dependencies: bool,
        use_repo_info: bool,
        use_unit_tests_info: bool,
        use_spec_info: bool,
        use_lint_info: bool,
    ) -> None:
        """Update the agent display with the given agent information."""
        info_items = [
            ("agent_name", "Agent", agent_name),
            ("model_name", "Model", model_name),
            ("run_tests", "Run Tests", run_tests),
            (
                "use_topo_sort_dependencies",
                "Topo Sort Dependencies",
                use_topo_sort_dependencies,
            ),
            ("use_repo_info", "Use Repo Info", use_repo_info),
            ("use_unit_tests_info", "Use Unit Tests", use_unit_tests_info),
            ("use_spec_info", "Use Spec", use_spec_info),
            ("use_lint_info", "Use Lint", use_lint_info),
        ]

        for attr_name, title, value in info_items:
            text = Text(f"{value}", justify="center")
            setattr(self, attr_name, text)
            self.layout["info"]["agent_info"][attr_name].update(
                Panel(text, title=title, border_style="blue")
            )

    def update_time_display(self, time_in_seconds: int) -> None:
        """Update the time display with the given time."""
        days, remainder = divmod(time_in_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        if days > 0:
            time_str = f"{days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"
        elif hours > 0:
            time_str = f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
        elif minutes > 0:
            time_str = f"{minutes:02d}m {seconds:02d}s"
        else:
            time_str = f"{seconds:02d}s"
        self.total_time_spent = time_in_seconds
        self.time_display = Text(f"{time_str}", justify="center")
        self.layout["progress"]["time"].update(
            Panel(self.time_display, title="Time Taken", border_style="blue")
        )

    def update_branch_display(self, branch: str) -> None:
        """Update the branch display with the given branch."""
        self.branch_name = branch
        self.branch_display = Text(f"{branch}", justify="center")
        self.layout["info"]["other_info"]["branch"].update(
            Panel(self.branch_display, title="Branch", border_style="blue")
        )

    def update_backend_display(self, backend: str) -> None:
        """Update the backend display with the given backend."""
        self.backend_display = Text(f"{backend}", justify="center")
        self.layout["info"]["other_info"]["backend"].update(
            Panel(self.backend_display, title="Backend", border_style="blue")
        )

    def update_log_dir_display(self, log_dir: str) -> None:
        """Update the log directory display with the given log directory."""
        self.log_dir_display = Text(f"{log_dir}", justify="center")
        self.layout["info"]["other_info"]["log_dir"].update(
            Panel(self.log_dir_display, title="Log Directory", border_style="blue")
        )

    def update_money_display(
        self, repo_name: str, file_name: str, money: float
    ) -> None:
        """Update the money display with the given money spent."""
        self.repo_money_spent.setdefault(repo_name, {}).setdefault(file_name, 0.0)
        self.repo_money_spent[repo_name][file_name] = money
        total_money_spent_for_all_repos = sum(
            sum(repo_money.values()) for repo_money in self.repo_money_spent.values()
        )
        self.money_display = Text(
            f"${total_money_spent_for_all_repos:.2f}",
            justify="center",
        )
        self.layout["progress"]["money"].update(
            Panel(Align.center(self.money_display), title="$$$$", border_style="blue")
        )

    def set_current_file(self, repo_name: str, file_name: str) -> None:
        """Set the current file for the given repository."""
        if repo_name not in self.ongoing_repos:
            # Start the repo if it's not yet tracked, but don't move it to the start
            self.start_repo(repo_name)

        # Just update the file name without reordering the repos
        self.ongoing_repos[repo_name] = file_name

        # Append the new file to finished files, keep the order intact
        self.finished_files.setdefault(repo_name, []).append(file_name)

        # Update the display
        self.update()

    def update(self) -> None:
        """Update the display with the current state of the repositories."""
        # Update not_started repos
        not_started_boxes = [RepoBox(repo, "red") for repo in self.not_started_repos]
        self.layout["main"]["left"]["not_started"].update(
            Panel(
                Columns(not_started_boxes),
                title="Not Started Repos",
                border_style="red",
            )
        )

        # Update finished repos
        finished_boxes = [RepoBox(repo, "green") for repo in self.finished_repos]
        self.layout["main"]["left"]["finished"].update(
            Panel(Columns(finished_boxes), title="Finished Repos", border_style="green")
        )

        # Update ongoing repos with progress bars
        ongoing_panels = [
            OngoingRepo(
                repo,
                self.ongoing_repos[repo],
                self.finished_files.get(repo, []),
                self.total_files_per_repo.get(repo, 1),
            )
            for repo in self.ongoing_repos
        ]

        if ongoing_panels:
            ongoing_layout = Layout()
            for i, panel in enumerate(ongoing_panels[: self.display_repo_progress_num]):
                ongoing_layout.add_split(Layout(panel, name=f"repo_{i}"))
            ongoing_layout.split_column(
                *[
                    ongoing_layout[f"repo_{i}"]
                    for i in range(
                        len(ongoing_panels[: self.display_repo_progress_num])
                    )
                ]
            )
            self.layout["main"]["right"].update(
                Panel(
                    ongoing_layout,
                    title=f"Ongoing(only show at most {self.display_repo_progress_num} repos, set with `--display_repo_progress_num` flag)",
                    border_style="yellow",
                )
            )
        else:
            self.layout["main"]["right"].update(
                Panel(
                    Text("Preparing to run repos..."),
                    title="Ongoing",
                    border_style="yellow",
                )
            )

    def start_repo(self, repo_name: str, total_files: int = 0) -> None:
        """Start a repository."""
        if repo_name in self.not_started_repos:
            self.not_started_repos.remove(repo_name)
        self.ongoing_repos[repo_name] = ""
        self.finished_files[repo_name] = []
        self.total_files_per_repo[repo_name] = total_files
        self.start_time_per_repo[repo_name] = time.time()
        self.update()

    def finish_repo(self, repo_name: str) -> None:
        """Finish a repository."""
        self.finished_repos.append(repo_name)
        if repo_name in self.ongoing_repos:
            del self.ongoing_repos[repo_name]
        if repo_name in self.finished_files:
            del self.finished_files[repo_name]
        self.overall_progress.update(self.overall_task, advance=1)
        self.end_time_per_repo[repo_name] = time.time()
        self.update()

    def set_not_started_repos(self, repos: list[str]) -> None:
        """Set the repositories that have not started."""
        self.not_started_repos = repos
        self.update()

    def __enter__(self):
        self.live = Live(
            self.layout, console=self.console, screen=True, refresh_per_second=4
        )
        self.live.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ):
        self.live.stop()
        print("\nSummary of Repository Processing:")
        print("-" * 80)
        print(
            f"{'Repository':<30} {'Time Taken':<15} {'Files Processed':<20} {'Money Spent':<15}"
        )
        print("-" * 80)
        total_files = 0
        total_money = 0
        for repo_name, end_time in self.end_time_per_repo.items():
            time_spent = end_time - self.start_time_per_repo[repo_name]
            files_processed = self.total_files_per_repo[repo_name]
            money_spent = sum(self.repo_money_spent.get(repo_name, {}).values())
            print(
                f"{repo_name:<30} {time_spent:>13.2f}s {files_processed:>18} {money_spent:>13.2f}$"
            )
            total_files += files_processed
            total_money += money_spent
        print("-" * 80)
        print(
            f"{'Total':<30} {self.total_time_spent:>13.2f}s {total_files:>18} {total_money:>13.2f}$"
        )
        print("-" * 80)

        # Write summary to JSON file

        summary_data = {
            "timestamp": datetime.now().isoformat(),
            "total_time_spent": self.total_time_spent,
            "total_files_processed": total_files,
            "total_money_spent": total_money,
            "repositories": [
                {
                    "name": repo_name,
                    "time_spent": self.end_time_per_repo[repo_name]
                    - self.start_time_per_repo[repo_name],
                    "files_processed": self.total_files_per_repo[repo_name],
                    "money_spent": sum(
                        self.repo_money_spent.get(repo_name, {}).values()
                    ),
                }
                for repo_name in self.end_time_per_repo
            ],
        }

        with open(
            f"processing_summary_{self.branch_name}.json",
            "w",
        ) as json_file:
            json.dump(summary_data, json_file, indent=4)

        print(
            f"\nSummary has been written to processing_summary_{self.branch_name}.json"
        )
