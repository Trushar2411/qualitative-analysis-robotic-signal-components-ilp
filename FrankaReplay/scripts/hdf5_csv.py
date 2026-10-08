import h5py
import numpy as np
import pandas as pd
from pathlib import Path
import argparse


def flatten_datasets(group, prefix=""):
    """Recursively extract numerical datasets from an HDF5 group."""
    data = {}

    for key, item in group.items():
        name = f"{prefix}/{key}" if prefix else key

        if isinstance(item, h5py.Group):
            data.update(flatten_datasets(item, name))

        elif isinstance(item, h5py.Dataset):
            # Ignore images and scalars before reading arrays into memory.
            if item.ndim not in (1, 2) or not np.issubdtype(item.dtype, np.number):
                continue
            values = np.asarray(item)

            if values.ndim == 0:
                continue

            if not np.issubdtype(values.dtype, np.number):
                continue

            if values.ndim == 1:
                data[name.replace("/", "_")] = values

            elif values.ndim == 2:
                for i in range(values.shape[1]):
                    data[f"{name.replace('/', '_')}_{i}"] = values[:, i]

    return data


def convert_hdf5_to_csv(input_file, output_dir, demos=None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with h5py.File(input_file, "r") as f:

        # Common demonstration structure
        if "data" in f:
            root = f["data"]
        else:
            root = f

        if demos:
            missing = set(demos) - set(root)
            if missing:
                raise ValueError(f"Unknown demonstrations: {sorted(missing)}")

        for demo_name, demo_group in root.items():

            if demos and demo_name not in demos:
                continue

            if not isinstance(demo_group, h5py.Group):
                continue

            print(f"Processing: {demo_name}")

            extracted = flatten_datasets(demo_group)

            if not extracted:
                print(f"No numerical data found in {demo_name}")
                continue

            # Retain only arrays with the same number of samples.
            # This avoids combining incompatible time dimensions.
            lengths = [len(v) for v in extracted.values()]
            target_length = max(set(lengths), key=lengths.count)

            extracted = {
                key: value
                for key, value in extracted.items()
                if len(value) == target_length
            }

            df = pd.DataFrame(extracted)

            output_file = output_dir / f"{demo_name}.csv"
            df.to_csv(output_file, index=False)

            print(f"Saved: {output_file}")
            print(f"Shape: {df.shape}")

    print("\nConversion completed!")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Convert HDF5 demonstrations into CSV files"
    )

    parser.add_argument("input", help="Path to input HDF5 file")

    parser.add_argument(
        "--output",
        default=Path(__file__).resolve().parents[1] / "data" / "converted",
        help="Output directory",
    )

    parser.add_argument(
        "--demo",
        action="append",
        help="Exact demonstration name; repeat to select several",
    )
    args = parser.parse_args()

    convert_hdf5_to_csv(args.input, args.output, args.demo)
