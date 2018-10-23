from setuptools import setup

setup(
    name="flow-python",
    version="0.6",
    package_dir={"flow": "src"},
    packages=["flow"],
    keywords=["spideroak", "flow", "semaphor"],
    author="Lucas Manuel Rodriguez",
    author_email="lucas@spideroak-inc.com",
    description="flow-python is a module to interact with the Flow stack.",
)
