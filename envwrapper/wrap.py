import argparse
import hashlib
import os
from pathlib import Path
import yaml
import re
from typing import Dict, NamedTuple

class Wrapper(NamedTuple):
    name: str
    header: str = "#!/bin/bash"
    footer: str = ""
    prefix: str = ""
    suffix: str = ""
    executor: str = "bash {script}"
    file_suffix: str = ".sh"

    def get_executor_cmd(self, scriptfile: str, stepname: str):
        return self.executor.format(script=scriptfile, stepname=stepname)

    def wrap(self, code: str, stepname: str):
        kw = {"stepname": stepname}
        header = self.header.format(**kw)
        prefix = self.prefix.format(**kw)
        code = code.format(**kw)
        suffix = self.suffix.format(**kw)
        footer = self.footer.format(**kw)
        return f"{header}\n{prefix}{code}{suffix}\n{footer}"

def parse_spec(path: Path):
    text = path.read_text()
    wrappers = []
    for obj in yaml.load_all(text, Loader=yaml.SafeLoader):
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
        stepname = f"{wrapper.name}_{hashlib.sha256(code.encode('utf8')).hexdigest()[:10]}"
        wrapped_code = wrapper.wrap(code, stepname)
        scriptfile = f"{stepname}_{hashlib.sha256(wrapped_code.encode('utf8')).hexdigest()}{wrapper.file_suffix}"
        scriptpath = scriptdir / scriptfile
        with scriptpath.open("w") as f:
            print(wrapped_code, file=f)

        code = wrapper.get_executor_cmd(scriptpath.absolute(), stepname)

    return code

def main():
    parser = argparse.ArgumentParser(description="Wraps the given code following the wrap specification and runs it")
    parser.add_argument("--scriptdir", type=Path, default=Path(".envwrapper"), help="directory in which the wrapped scripts are generated, relative to the workdir")
    parser.add_argument("--workdir", type=Path, default=Path("."), help="working directory in which the scripts are run")
    parser.add_argument("--spec", type=Path, help="specification for wrapping")
    parser.add_argument("-n", "--just-print", action="store_true", help="do not execute the code, just print what command to run")
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

    if args.just_print:
        print(code)

    else:
        os.system(code)

if __name__ == "__main__":
    main()
