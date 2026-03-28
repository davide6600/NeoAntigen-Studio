import subprocess
import os

env = os.environ.copy()
env["PYTHONPATH"] = "."

with open('pytest_out.txt', 'w', encoding='utf-8') as f:
    subprocess.run(['pytest', 'tests/', '-v', '--tb=short'], stdout=f, stderr=f, env=env)
