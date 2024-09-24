from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, ProgressColumn, Task
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.columns import Columns
from rich.style import Style
from rich.rule import Rule
from rich.align import Align
from collections import deque, OrderedDict
from types import TracebackType

class RepoBox:
    def __init__(self, name: str, style: str):
        self.name = name
        self.style = style

    def __rich__(self):
        return Panel(Text(self.name, style=self.style), expand=False, border_style=self.style)

class RepoProgressColumn(ProgressColumn):
    def render(self, task: Task) -> Text:
        return Text(f"{int(task.completed or 0)}/{int(task.total or 1)}")

class OngoingRepo:
    def __init__(self, name: str, current_file: str, finished_files: list[str], total_files: int):
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
        task_id = progress.add_task("", total=self.total_files, completed=len(self.finished_files))

        content = [
            Text(f"Current working file:", style="bold"),
            Text(self.current_file, style="green"),
            Rule(style="dim"),
            Text("Finished files (recent 5):", style="bold"),
        ] + [Text(file, style="dim green") for file in self.finished_files[-6:-1]]
        return Panel(Group(progress, *content), title=self.name, border_style="yellow", expand=True)

class TerminalDisplay:
    def __init__(self, total_repos: int):
        self.console = Console()
        self.total_repos = total_repos
        self.unstarted_repos = []
        self.finished_repos = []
        self.ongoing_repos = OrderedDict()
        self.finished_files = {}
        self.total_files_per_repo = {}

        self.overall_progress = Progress(
            SpinnerColumn(),
            BarColumn(bar_width=None),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        )
        self.overall_task = self.overall_progress.add_task("[green]Processing", total=total_repos)
        
        self.layout = Layout()
        self.layout.split_column(
            Layout(name="progress", ratio=1),
            Layout(name="main", ratio=14),
        )
        self.layout["progress"].split_row(
            Layout(name="pbar", ratio=4),
            Layout(name="backend", ratio=1),
            Layout(name="money", ratio=1),
        )
        self.layout["progress"]["pbar"].update(Panel(self.overall_progress, title="Overall Progress", border_style="blue"))
        self.backend_display = Text(f"Backend Using: ", justify="center")
        self.layout["progress"]["backend"].update(Panel(self.backend_display, title="Backend", border_style="cyan"))
        self.money_display = Text(f"Money Spent So Far: $0.00", justify="center")
        self.layout["progress"]["money"].update(Panel(self.money_display, title="$$$$", border_style="cyan"))
        self.layout["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1),
        )
        self.layout["main"]["left"].split_column(
            Layout(name="unstarted", ratio=1),
            Layout(name="finished", ratio=1),
        )
        self.layout["right"].update(Panel(Layout(name="ongoing"), title="Ongoing", border_style="yellow"))
        
        # Initialize panels with empty content
        self.layout["left"]["unstarted"].update(Panel(Text(""), title="Unstarted Repos", border_style="red"))
        self.layout["left"]["finished"].update(Panel(Text(""), title="Finished Repos", border_style="green"))
        
    def update_backend_display(self, backend: str):
        self.backend_display = Text(f"Backend Using: {backend}", justify="center")
        self.layout["progress"]["backend"].update(Panel(self.backend_display, title="Backend", border_style="green"))

    def update_money_display(self, money: float):
        self.money_display = Text(f"Money Spent So Far: ${money:.2f}", justify="center")
        self.layout["progress"]["money"].update(Panel(Align.center(self.money_display), title="$$$$"))

    def set_current_file(self, repo_name: str, file_name: str):
        if repo_name not in self.ongoing_repos:
            # Start the repo if it's not yet tracked, but don't move it to the start
            self.start_repo(repo_name)
        
        # Just update the file name without reordering the repos
        self.ongoing_repos[repo_name] = file_name
        
        # Append the new file to finished files, keep the order intact
        self.finished_files.setdefault(repo_name, []).append(file_name)

        # Update the display
        self.update()
    
    def update(self):
        # Update unstarted repos
        unstarted_boxes = [RepoBox(repo, "red") for repo in self.unstarted_repos]
        self.layout["left"]["unstarted"].update(Panel(Columns(unstarted_boxes), title="Not Started Repos", border_style="red"))

        # Update finished repos
        finished_boxes = [RepoBox(repo, "green") for repo in self.finished_repos]
        self.layout["left"]["finished"].update(Panel(Columns(finished_boxes), title="Finished Repos", border_style="green"))

        # Update ongoing repos with progress bars
        ongoing_panels = [OngoingRepo(repo, self.ongoing_repos[repo], self.finished_files.get(repo, []), self.total_files_per_repo.get(repo, 1)) for repo in self.ongoing_repos]

        if ongoing_panels:
            ongoing_layout = Layout()
            for i, panel in enumerate(ongoing_panels):
                ongoing_layout.add_split(Layout(panel, name=f"repo_{i}"))
            ongoing_layout.split_column(*[ongoing_layout[f"repo_{i}"] for i in range(len(ongoing_panels))])
            self.layout["right"].update(Panel(ongoing_layout, title="Ongoing", border_style="yellow"))
        else:
            self.layout["right"].update(Panel(Text("No ongoing repos"), title="Ongoing", border_style="yellow"))

    def start_repo(self, repo_name: str, total_files: int = 0):
        if repo_name in self.unstarted_repos:
            self.unstarted_repos.remove(repo_name)
        self.ongoing_repos[repo_name] = ""
        self.finished_files[repo_name] = []
        self.total_files_per_repo[repo_name] = total_files
        self.update()
        
    def finish_repo(self, repo_name: str):
        self.finished_repos.append(repo_name)
        if repo_name in self.ongoing_repos:
            del self.ongoing_repos[repo_name]
        if repo_name in self.finished_files:
            del self.finished_files[repo_name]
        self.overall_progress.update(self.overall_task, advance=1)
        self.update()
        
    def set_unstarted_repos(self, repos: list[str]):
        self.unstarted_repos = repos
        self.update()
        
    def __enter__(self):
        self.live = Live(self.layout, console=self.console, screen=True, refresh_per_second=4)
        self.live.start()
        return self
        
    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None):
        self.live.stop()