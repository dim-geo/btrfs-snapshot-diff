# btrfs-snapshot-diff
Find the differences between btrfs snapshots

Btrfs, as a CoW filesystem, has a problem identifying the size of a snapshot and the differences between snapshots.
By using [python-btrfs](https://github.com/knorrie/python-btrfs), it is possible to parse the metadata of a btrfs filesystem and find the differences between subvolumes/snapshots.

## Currently implemented functionality:

This tool can approximately identify how much space will be freed when a snapshot is deleted.

## How it works:

This tool identifies all subvolumes of a btrfs filesystem. For each subvolume all file extents which are not inline are parsed and kept. All other items are ignored.

Thus, we acquire a dictionary of chronologically ordered snapshots together with their set of file extents:

1. Snapshot 1
   1. file extent 1
   2. file extent 2
   3. ...
   4. file extent n
2. Snapshot 2
   1. file extent 1
   2. file extent 2
   3. ...
   4. file extent n
3. Snapshot n
   1. ...

Now, the actual disk size of Snapshot 1 is the size of the extents of snapshot 1 minus the common extents with snapshot 2. (Set(Snapshot1) - Set(Snapshot2))
The actual disk size of Snapshot 2 is the size of the extents of snapshot 2 minus the common extents with snapshot 1 minus the common extents with snapshot 3. (Set(Snapshot2) - Set(Snapshot1)) - Set(Snapshot3)

## Usage:

## Possible expansions:

## Open questions:
