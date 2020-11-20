import os
import sys
import shutil
import argparse


def main():
    parser = argparse.ArgumentParser(description="MLCube Cookie Cutter")
    parser.add_argument("--root-dir", "--root_dir", type=str, help="Root directory of the new MLCube",
                        default="mlcube_example")
    args = parser.parse_args()

    if os.path.isdir(args.root_dir):
        print(f"Path already exists: {args.root_dir}")
        sys.exit(1)

    template_path = os.path.join(
      os.path.dirname(os.path.realpath(__file__)),
      "template"
    )
    shutil.copytree(template_path, args.root_dir)
    print(f"Template MLCube created at {args.root_dir}")


if __name__ == "__main__":
    main()
