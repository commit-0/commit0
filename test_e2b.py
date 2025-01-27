from dotenv import load_dotenv
load_dotenv()
from e2b_code_interpreter import Sandbox

sb = Sandbox()
sb.commands.run("pip install commit0")
sb.commands.run("commit0 setup tinydb")
import pdb; pdb.set_trace()
k
