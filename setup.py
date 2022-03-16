import setuptools

setuptools.setup(
    name="pyjmap",
    version="1.0.0-beta",
    author="Aurum",
    url="https://github.com/SunakazeKun/pyjmap",
    description="Python library for Nintendo's BCSV/JMap format",
    keywords=["nintendo", "jsystem", "jmap", "bcsv", "modding"],
    packages=setuptools.find_packages(),
    python_requires=">=3.6",
    license="gpl-3.0",
    classifiers=[
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "License :: OSI Approved :: GNU General Public License v3.0",
        "Programming Language :: Python :: 3 :: Only"
    ],
    entry_points={
        "console_scripts": [
            "pyjmap = pyjmap.__main__:main"
        ]
    }
)
