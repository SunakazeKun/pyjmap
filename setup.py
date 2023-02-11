import setuptools

with open("README.md", "r") as f:
    README = f.read()

setuptools.setup(
    name="pyjmap",
    version="1.0.9",
    author="Aurum",
    url="https://github.com/SunakazeKun/pyjmap",
    description="Python library for Nintendo's BCSV/JMap format",
    long_description=README,
    long_description_content_type="text/markdown",
    keywords=["nintendo", "jsystem", "jmap", "bcsv", "modding"],
    packages=setuptools.find_packages(),
    package_data={"pyjmap": ["lookup_*.txt"]},
    python_requires=">=3.6",
    license="gpl-3.0",
    classifiers=[
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3 :: Only"
    ],
    entry_points={
        "console_scripts": [
            "pyjmap = pyjmap.__main__:main"
        ]
    }
)
