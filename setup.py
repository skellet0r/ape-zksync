from setuptools import setup

extras = {
    "lint": [
        "black",
        "flake8",
        "isort",
        "mypy",
    ],
    "dev": [
        "pre-commit",
    ],
}

extras["dev"] += extras["lint"]

setup(
    name="ape-zksync",
    use_scm_version=True,
    setup_requires=["setuptools_scm"],
    install_requires=["eth-ape>=0.4.0,<0.5", "importlib-metadata ; python_version<'3.8'"],
    python_requires=">=3.7.2,<4",
    extras_require=extras,
    packages=["ape_zksync"],
)
