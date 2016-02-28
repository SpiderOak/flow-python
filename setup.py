from setuptools import setup, find_packages

setup(name = "flow-python",
      version = "0.1",
      package_dir = { "flow": "src" },
      packages = [ "flow" ],
      install_requires = [ "requests" ],
      keywords = [ "spideroak", "flow", "semaphor" ],
      author = "Lucas Manuel Rodriguez",
      author_email = "lucas@spideroak-inc.com",
      description = "flow-python is a module to "\
                    "interact with the Flow stack.",
)
