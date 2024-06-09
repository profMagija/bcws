import click
import os


@click.command()
@click.argument("source", type=click.Path(exists=True))
@click.argument("target", type=click.Path())
def snip(source: str, target: str):
    _snip_element(source, target)


def _snip_element(source: str, target: str):
    if os.path.isdir(source):
        _snip_directory(source, target)
    else:
        _snip_file(source, target)


def _snip_directory(source: str, target: str):
    if not os.path.exists(target):
        os.makedirs(target)
    elif not os.path.isdir(target):
        raise ValueError(f"{target} is not a directory")

    for elem in os.listdir(source):
        _snip_element(os.path.join(source, elem), os.path.join(target, elem))


def _snip_file(source: str, target: str):
    with open(source, "r") as f:
        lines = f.readlines()

    writing = True

    with open(target, "w") as f:
        for line in lines:
            if "# <<" in line:
                line = line.replace("# <<", "")
            if "----8<----" in line:
                writing = not writing
            elif writing:
                f.write(line)

    print(f"Snipped {source} to {target}")


if __name__ == "__main__":
    snip()
