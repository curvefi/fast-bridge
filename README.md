# Contributing
## Install
```shell
uv sync
source .venv/bin/activate

# Update OApp and remove redundant files
git submodule update --init --recursive --depth 1
find contracts/modules/oapp_vyper -mindepth 1 -maxdepth 1 ! -name 'src' -exec rm -rf {} +
```

## Tests
```shell
uv run pytest tests/
```
