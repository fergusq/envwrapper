import argparse
import hashlib
from pathlib import Path
import yaml
import re
from typing import Dict, NamedTuple

class Wrapper(NamedTuple):
    name: str
    header: str
    footer: str = ""
    prefix: str = ""
    suffix: str = ""
    executor: str = "{script}"
    file_suffix: str = ".sh"

    def get_executor_cmd(self, scriptfile: str):
        return self.executor.format(script=scriptfile)

    def wrap(self, code: str):
        return f"{self.header}\n{self.prefix}{code}{self.suffix}\n{self.footer}"

def parse_spec(path: Path):
    text = path.read_text()
    wrappers = []
    for obj in yaml.load_all(text):
        wrappers.append(Wrapper(**obj))

    return {wrapper.name: wrapper for wrapper in wrappers}

def wrap(spec: Dict[str, Wrapper], scriptdir: Path, workdir: Path, code: str):
    workdir.cwd()

    wrappers = []
    while m := re.match(r"\s*#WRAP\((\w+)\)", code):
        wrapper_name = m.group(1)
        code = code[m.span()[1]:]
        assert wrapper_name in spec, f"{wrapper_name} not found in spec"
        wrappers.append(wrapper_name)

    wrappers.append("innermost")

    for wrapper_name in reversed(wrappers):
        wrapper = spec[wrapper_name]
        wrapped_code = wrapper.wrap(code)
        scriptfile = f"{hashlib.sha256(wrapped_code.encode('utf8')).hexdigest()}{wrapper.file_suffix}"
        with (scriptdir / scriptfile).open("w") as f:
            print(wrapped_code, file=f)

        code = wrapper.get_executor_cmd((scriptdir / scriptfile).absolute())

    return code

def main():
    parser = argparse.ArgumentParser(description="Wraps the given code following the wrap specification and runs it")
    parser.add_argument("--scriptdir", type=Path, default=Path(".envwrapper"), help="directory in which the wrapped scripts are generated, relative to the workdir")
    parser.add_argument("--workdir", type=Path, default=Path("."), help="working directory in which the scripts are run")
    parser.add_argument("--spec", type=Path, help="specification for wrapping")
    parser.add_argument("code", type=str, help="code to be wrapped")
    args = parser.parse_args()

    scriptdir: Path = args.scriptdir
    workdir: Path = args.workdir

    if not scriptdir.exists():
        scriptdir.mkdir()

    spec = parse_spec(args.spec)
    assert scriptdir.is_dir()
    assert workdir.is_dir()

    if "innermost" not in spec:
        spec["innermost"] = Wrapper(name="innermost", header="#!/bin/bash")

    code = wrap(spec, scriptdir, workdir, args.code)

    print("EXECUTE:", repr(code))

if __name__ == "__main__":
    main()
