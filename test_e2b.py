from dotenv import load_dotenv
load_dotenv()
from e2b_code_interpreter import Sandbox

sb = Sandbox()
# install uv
sb.commands.run("curl -LsSf https://astral.sh/uv/install.sh | sh")
sb.commands.run("pip install git+https://github.com/commit-0/commit0.git@justin/e2b")
# run setup script
# copy diff
# run eval script
execution = sb.commands.run("commit0 setup tinydb")
print(execution.stdout)
execution = sb.commands.run("commit0 test simpy tests/test_event.py::test_succeed --reference --backend e2b")
print(execution.stdout)
execution = sb.commands.run("commit0 test simpy tests/test_event.py::test_succeed --backend e2b")
print(execution.stdout)
import pdb; pdb.set_trace()
