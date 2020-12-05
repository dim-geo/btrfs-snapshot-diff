# btrfs-snapshot-diff
Find the differences between btrfs snapshots, no quota activation in btrfs needed!

Btrfs, as a CoW filesystem, has a problem identifying the size of a snapshot and the differences between snapshots.
By using [python-btrfs](https://github.com/knorrie/python-btrfs), it is possible to parse the metadata of a btrfs filesystem and find the differences between subvolumes/snapshots.

## Currently implemented functionality:

This tool can approximately identify how much space will be freed when a snapshot is deleted.

## How it works:

This tool identifies all subvolumes of a btrfs filesystem. For each subvolume all file extents which are not inline are parsed and kept. All other items are ignored.

Thus, we create a tree of extents & ranges together with the snapshots that use them:

1. file extent 1
   1. range1: [Snapshot 1, Snapshot 2]
   2. range2: [Snapshot 3]
   3. ...
2. file extent 2
   1. range1: [...]
   2. range2: [...]

Now, the actual disk size of Snapshot 1 can be extracted from each file extent
## Usage:

[python-btrfs](https://github.com/knorrie/python-btrfs) must be installed.

Program is single threaded, it could use a lot of memory and it puts a lot of read stress in disks. It could take many minutes. ionice it & monitor its memory usage. Memory usage & execution time depend on the dataset. The program does not perform any write operations. Do not modify subvolume/snapshot during execution. Try not to write any data to any subvolume or execute dedup programs in parallel.

`subvolume.py [-u] [-f] [-r <root tree, default 5>] /path/to/btrfs/ [ -i | -o ] [<subvolume id1> <subvolume id2>]`

`-u` calculates the unique data occupied by each snapshot. Thus, `-r` makes no sense. Specifying subvolumes to ignore can mess with `-u` results because the specified subvolume data will not be parsed!
`-f` finds the files that might contribute to the unique extents.
`-i` makes the program to ignore the specified subvolumes, which is also the default behaviour if no `-i` or `-o` argument is specified but subvolumes are given.
`-o` makes the program to analyze only the specified subvolumes.

You can find subvolume ids by using:
`btrfs subvolume list /path/to/btrfs`

## Example:

`btrfs subvolume list /path/to/btrfs`:

```
ID 258 gen 15649 top level 5 path mydata
ID 259 gen 15651 top level 5 path subvol_snapshots
ID 1949 gen 3785 top level 259 path subvol_snapshots/283/snapshot
ID 2133 gen 5080 top level 259 path subvol_snapshots/435/snapshot
ID 2395 gen 6616 top level 259 path subvol_snapshots/660/snapshot
ID 2694 gen 8781 top level 259 path subvol_snapshots/888/snapshot
ID 3661 gen 10830 top level 259 path subvol_snapshots/1126/snapshot
ID 3818 gen 11948 top level 259 path subvol_snapshots/1228/snapshot
ID 3887 gen 12351 top level 259 path subvol_snapshots/1285/snapshot
ID 3942 gen 12628 top level 259 path subvol_snapshots/1333/snapshot
ID 4040 gen 13778 top level 259 path subvol_snapshots/1412/snapshot
ID 4072 gen 13778 top level 259 path subvol_snapshots/1438/snapshot
ID 4091 gen 13778 top level 259 path subvol_snapshots/1452/snapshot
ID 4130 gen 13853 top level 259 path subvol_snapshots/1477/snapshot
ID 4166 gen 14537 top level 259 path subvol_snapshots/1509/snapshot
ID 4182 gen 14537 top level 259 path subvol_snapshots/1523/snapshot
ID 4196 gen 14537 top level 259 path subvol_snapshots/1535/snapshot
ID 4211 gen 14753 top level 259 path subvol_snapshots/1545/snapshot
ID 4258 gen 15274 top level 259 path subvol_snapshots/1582/snapshot
ID 4337 gen 15274 top level 259 path subvol_snapshots/1652/snapshot
ID 4372 gen 15274 top level 259 path subvol_snapshots/1680/snapshot
ID 4392 gen 15341 top level 259 path subvol_snapshots/1691/snapshot
ID 4414 gen 15434 top level 259 path subvol_snapshots/1712/snapshot
ID 4444 gen 15538 top level 259 path subvol_snapshots/1740/snapshot
ID 4451 gen 15566 top level 259 path subvol_snapshots/1747/snapshot
ID 4452 gen 15570 top level 259 path subvol_snapshots/1748/snapshot
ID 4454 gen 15581 top level 259 path subvol_snapshots/1749/snapshot
ID 4455 gen 15584 top level 259 path subvol_snapshots/1750/snapshot
ID 4456 gen 15589 top level 259 path subvol_snapshots/1751/snapshot
ID 4457 gen 15592 top level 259 path subvol_snapshots/1752/snapshot
ID 4458 gen 15596 top level 259 path subvol_snapshots/1753/snapshot
ID 4459 gen 15598 top level 259 path subvol_snapshots/1754/snapshot
ID 4460 gen 15611 top level 259 path subvol_snapshots/1755/snapshot
ID 4461 gen 15612 top level 259 path subvol_snapshots/1756/snapshot
ID 4462 gen 15620 top level 259 path subvol_snapshots/1757/snapshot
ID 4463 gen 15639 top level 259 path subvol_snapshots/1758/snapshot
ID 4464 gen 15643 top level 259 path subvol_snapshots/1759/snapshot
ID 4465 gen 15646 top level 259 path subvol_snapshots/1760/snapshot
ID 4466 gen 15649 top level 259 path subvol_snapshots/1761/snapshot
```

`subvolume.py -r 258 /path/to/btrfs/ 259`:

```
 Unique File Extents  Extents added ontop   Extents added ontop of
 per       subvolume  of previous subvolume current(act) subvolume
---------------------|---------------------|----------------------
SubvolumId       Size                  Size                   Size
       258      0.00B                 0.00B                1.46TiB
      4466      0.00B                 0.00B                  0.00B
      4465      0.00B                 0.00B                  0.00B
      4464      0.00B                 0.00B                  0.00B
      4463      0.00B               2.58MiB                  0.00B
      4462      0.00B                 0.00B              648.00KiB
      4461      0.00B                 0.00B              648.00KiB
      4460      0.00B               1.18MiB              648.00KiB
      4459      0.00B                 0.00B              996.00KiB
      4458      0.00B                 0.00B              996.00KiB
      4457      0.00B                 0.00B              996.00KiB
      4456      0.00B                 0.00B              996.00KiB
      4455      0.00B                 0.00B              996.00KiB
      4454      0.00B                 0.00B              996.00KiB
      4452      0.00B                 0.00B              996.00KiB
      4451      0.00B                 0.00B              996.00KiB
      4444      0.00B               1.23MiB              996.00KiB
      4414  120.00KiB              12.38MiB                1.07MiB
      4392  184.00KiB               6.20GiB                1.19MiB
      4372  164.00KiB               3.64MiB                4.41MiB
      4337  176.00KiB               6.47MiB                4.48MiB
      4258      0.00B            1010.53MiB                4.91MiB
      4211      0.00B               1.97GiB                4.91MiB
      4196   36.00KiB              36.00KiB                5.64MiB
      4182   36.00KiB               3.66MiB                5.64MiB
      4166  140.00KiB             590.95MiB                5.80MiB
      4130  192.00KiB               6.04GiB                5.83MiB
      4091    1.75MiB              34.36MiB                7.49MiB
      4072  296.00KiB               9.12MiB                8.09MiB
      4040    8.96MiB              11.01GiB               16.72MiB
      3942    2.31MiB               4.16GiB                8.67MiB
      3887    1.59MiB               4.15GiB               27.33MiB
      3818    1.22MiB              15.20GiB               27.41MiB
      3661    2.43MiB              13.61GiB               27.43MiB
      2694    3.19MiB              40.44GiB               27.42MiB
      2395    6.55MiB              13.25GiB               62.80MiB
      2133    5.99MiB              17.44GiB              119.27MiB
      1949   42.48MiB               1.33TiB              166.50MiB
Size/Cost of snapshots: 77.78MiB Volatility: 0.01%
```
Snapshot 2133 introduced 17GiB, where most of them still reside on the system (used by newer snapshot, 2395)
Thus, deleting snapshot 2133, will only free 6MiB. Snapshot 2133 has 119MiB changed compared to current/ active (258) subvolume.
When using `-u` argument only the first column has values.

Files result example:
```
Possible Unique Files:
beeshash.dat/ : {4652}
beescrawl.dat/ : {4652}
beesstats.txt/ : {4652}
2708/filelist-2700.txt/ : {259}
2744/filelist-2741.txt/ : {259}
2752/filelist-2744.txt/ : {259}
2795/filelist-2789.txt/ : {259}
```


## Possible expansions:

Calculate the size of metadata block differences.
Take into consideration inline file extents.
Why do we recieve the same extent with the same range many times?
