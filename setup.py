from setuptools import setup

try:
    from pip.req import parse_requirements
except ImportError:
    print("The 'pip' package is needed for the setup")
    exit(1)

reqs = parse_requirements("requirements.txt", session=False)
install_requires = [str(ir.req) for ir in reqs]

setup(
    name="flow-python",
    version="0.6",
    package_dir={"flow": "src"},
    packages=["flow"],
    install_requires=install_requires,
    keywords=["spideroak", "flow", "semaphor"],
    author="Lucas Manuel Rodriguez",
    author_email="lucas@spideroak-inc.com",
    description="flow-python is a module to interact with the Flow stack.",
)
