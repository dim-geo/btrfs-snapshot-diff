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

[python-btrfs](https://github.com/knorrie/python-btrfs) must be installed.

`subvolume.py /path/to/btrfs <subvolume id to ignore1> <subvolume id to ignore2> ...`

You can find suvolume ids by using:
`btrfs subvolume list /path/to/btrfs`

## Example:

`btrfs subvolume list /path/to/btrfs`:

```
ID 258 gen 14468 top level 5 path mydata
ID 259 gen 14467 top level 5 path subvol_snapshots
ID 1949 gen 3785 top level 259 path subvol_snapshots/283/snapshot
ID 2133 gen 5080 top level 259 path subvol_snapshots/435/snapshot
ID 2395 gen 6616 top level 259 path subvol_snapshots/660/snapshot
ID 2577 gen 8480 top level 259 path subvol_snapshots/783/snapshot
ID 2694 gen 8781 top level 259 path subvol_snapshots/888/snapshot
ID 3661 gen 10830 top level 259 path subvol_snapshots/1126/snapshot
ID 3764 gen 11594 top level 259 path subvol_snapshots/1189/snapshot
ID 3818 gen 11948 top level 259 path subvol_snapshots/1228/snapshot
ID 3857 gen 12035 top level 259 path subvol_snapshots/1258/snapshot
ID 3864 gen 12070 top level 259 path subvol_snapshots/1265/snapshot
ID 3887 gen 12351 top level 259 path subvol_snapshots/1285/snapshot
ID 3900 gen 12404 top level 259 path subvol_snapshots/1298/snapshot
ID 3913 gen 12505 top level 259 path subvol_snapshots/1311/snapshot
ID 3923 gen 12557 top level 259 path subvol_snapshots/1320/snapshot
ID 3942 gen 12628 top level 259 path subvol_snapshots/1333/snapshot
ID 3974 gen 13105 top level 259 path subvol_snapshots/1362/snapshot
ID 4040 gen 13778 top level 259 path subvol_snapshots/1412/snapshot
ID 4046 gen 13778 top level 259 path subvol_snapshots/1417/snapshot
ID 4072 gen 13778 top level 259 path subvol_snapshots/1438/snapshot
ID 4091 gen 13778 top level 259 path subvol_snapshots/1452/snapshot
ID 4130 gen 13853 top level 259 path subvol_snapshots/1477/snapshot
ID 4166 gen 14444 top level 259 path subvol_snapshots/1509/snapshot
ID 4175 gen 14444 top level 259 path subvol_snapshots/1517/snapshot
ID 4176 gen 14444 top level 259 path subvol_snapshots/1518/snapshot
ID 4177 gen 14444 top level 259 path subvol_snapshots/1519/snapshot
ID 4178 gen 14444 top level 259 path subvol_snapshots/1520/snapshot
ID 4179 gen 14444 top level 259 path subvol_snapshots/1521/snapshot
ID 4181 gen 14444 top level 259 path subvol_snapshots/1522/snapshot
ID 4182 gen 14444 top level 259 path subvol_snapshots/1523/snapshot
ID 4183 gen 14450 top level 259 path subvol_snapshots/1524/snapshot
ID 4184 gen 14455 top level 259 path subvol_snapshots/1525/snapshot
ID 4185 gen 14459 top level 259 path subvol_snapshots/1526/snapshot
ID 4186 gen 14464 top level 259 path subvol_snapshots/1527/snapshot
```

`python subvolume.py /path/to/btrfs 259`:

```
Unique File Extents Extents added ontop Extents added    ontop
per       subvolume of older  subvolume of current(act) subvolume
-------------------|-------------------|----------------------
SubvolumId     Size SubvolumId     Size SubvolumId     Size
       258     0.0B        258     0.0B        258   1.6TiB
      4186     0.0B       4186     0.0B       4186     0.0B
      4185     0.0B       4185     0.0B       4185     0.0B
      4184     0.0B       4184     0.0B       4184     0.0B
      4183     0.0B       4183     0.0B       4183     0.0B
      4182     0.0B       4182     0.0B       4182     0.0B
      4181     0.0B       4181     0.0B       4181     0.0B
      4179     0.0B       4179     0.0B       4179     0.0B
      4178     0.0B       4178   3.3MiB       4178     0.0B
      4177     0.0B       4177     0.0B       4177 188.0KiB
      4176     0.0B       4176     0.0B       4176 188.0KiB
      4175     0.0B       4175     0.0B       4175 188.0KiB
      4166     0.0B       4166 590.9MiB       4166 188.0KiB
      4130   8.0KiB       4130   6.1GiB       4130 164.0KiB
      4091   4.0KiB       4091  34.0MiB       4091   2.9MiB
      4072     0.0B       4072   4.8MiB       4072   3.0MiB
      4046  12.0KiB       4046   3.8MiB       4046   3.1MiB
      4040   8.4MiB       4040  11.0GiB       4040  11.6MiB
      3974  20.0KiB       3974   2.1MiB       3974   4.7MiB
      3942 128.0KiB       3942   3.9GiB       3942   4.8MiB
      3923     0.0B       3923  96.5MiB       3923  11.3MiB
      3913     0.0B       3913 556.4MiB       3913  11.3MiB
      3900     0.0B       3900  36.3MiB       3900   4.6MiB
      3887     0.0B       3887 995.6MiB       3887   4.6MiB
      3864     0.0B       3864  61.9MiB       3864   4.6MiB
      3857     0.0B       3857   3.1GiB       3857   4.6MiB
      3818  32.0KiB       3818   7.3GiB       3818   4.6MiB
      3764 116.0KiB       3764   7.9GiB       3764   4.9MiB
      3661 216.0KiB       3661  13.6GiB       3661   5.1MiB
      2694   8.0KiB       2694 590.7MiB       2694   4.8MiB
      2577   2.4MiB       2577  39.9GiB       2577   7.3MiB
      2395   1.7MiB       2395  54.2GiB       2395  53.5MiB
      2133 447.7MiB       2133  28.3GiB       2133   2.4GiB
      1949 151.0MiB       1949   1.4TiB       1949   2.1GiB
```
Snapshot 2133 introduced 28GiB, where most of them still reside on the system (used by newer snapshot, 2395)
Thus, deleting snapshot 2133, will only free 447MiB. Snapshot 2133 has 2.4GiB changed compared to current (258) subvolume.

## Possible expansions:

Calculate the size of metadata block differences.
Take into consideration inline file extents.
Does balance operation change the differences between snapshots?
