# Contributing

The repository for this project is
[https://github.com/ISISComputingGroup/fastcs-secop](https://github.com/ISISComputingGroup/fastcs-secop).

Contributions via GitHub issues and pull requests are welcome. If an issue or PR appears to have been ignored, it may have
simply been missed - email [ISISExperimentControls@stfc.ac.uk](mailto:ISISExperimentControls@stfc.ac.uk) if an issue
or PR appears to have been ignored accidentally.

Some changes may require preparatory changes in [FastCS itself](https://github.com/DiamondLightSource/fastcs).

## Developer installation

To install a developer version of the library, run `pip install -e .[dev]` in a python virtual environment. 
You can also use `uv pip install -e .[dev]` if you have the [`uv`](https://docs.astral.sh/uv/) tool installed.

## Linting

Linting is performed by [ruff](https://docs.astral.sh/ruff/) (formatting & linting) and
[pyright](https://github.com/microsoft/pyright) (type-checking).

```shell
ruff format
ruff check --fix
pyright
```

## Documentation

Documentation is built using [sphinx](https://www.sphinx-doc.org/en/master/).
To get a local development build of the docs, use `sphinx-autobuild doc _build --watch src`.

Spell checking is run automatically in CI - if a word is correctly spelt but the spellchecker flags it,
add the word to `doc/spelling_wordlist.txt`.

The spellchecker can be run manually using `sphinx-build -E -a -W --keep-going -b spelling doc _build` - this is best
run on a Windows machine due to differences in the system spelling dictionary between operating systems.

## Tests

Tests run via `pytest`. Some tests spawn a very basic lewis emulator on port 57677 to test a full communication
scenario. This is handled automatically by pytest, but may fail if port 57677 is already in use.
