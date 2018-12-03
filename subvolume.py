#!/usr/bin/python3

#    Copyright (C) 2018  Dimitris Georgiou

#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.

#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.


import btrfs
import os
import sys
import multiprocessing

def sizeof_fmt(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


class Snapshot:
    def __init__(self, objectid):
        self._objectid = objectid
        self._blocks=set()

    @property
    def objectid(self):
        return self._objectid
    
    @property
    def blocks(self):
        return self._blocks

    def add(self,objectid,offset,size):
        pair=(objectid,offset,size)
        self._blocks.add(pair)

    def _setblocks(self,data):
        self._blocks=data

    def __sub__(self,other):
        leftover_blocks=self.blocks-other.blocks
        newsnapshot=Snapshot(self.objectid)
        newsnapshot._setblocks(leftover_blocks)
        return newsnapshot
    
    @property
    def size(self):
        sum=0
        for extent in self.blocks:
            sum+=extent[2]
        return sum
    
    def __str__(self):
        return '{:>10} {:>8}'.format(self.objectid,sizeof_fmt(self.size))
        

def find_extents(pair):
  fd,tree = pair
  snapshot=Snapshot(tree)
  #search in this subvolume all file extents
  for header, data in btrfs.ioctl.search_v2(fd, tree):
    if header.type == btrfs.ctree.EXTENT_DATA_KEY:
      datum=btrfs.ctree.FileExtentItem(header,data)
      #print(datum)
      #ignore inline file extents, they are small
      if datum.type != btrfs.ctree.FILE_EXTENT_INLINE:
        snapshot.add(header.objectid,datum.logical_offset,datum.disk_num_bytes)
  return snapshot


if __name__ == "__main__":
    #path of btrfs filesystem
    path = sys.argv[1]
    
    #list of ingored subvolumes
    ignored_trees=set()

    for item in sys.argv[2:]:
        ignored_trees.add(int(item))

    fs = btrfs.FileSystem(path)
    subvolume_list=[]

    #iterate all subvolumes
    arguments=[]
    for subvol in fs.subvolumes():
        tree = subvol.key.objectid
        if tree not in ignored_trees:
            arguments.append((fs.fd,tree))
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        subvolume_list=pool.map(find_extents,arguments)

    #make sure that subvolume order is from newest (current) to oldest

    current_subvolume=subvolume_list[0]
    del subvolume_list[0]
    subvolume_list.append(current_subvolume)
    subvolume_list.reverse()

    #parse list of subvolumes and calculate the number of the unique file extents in this subvolume
    #calculate also how much data were changed, compared to the older subvolume
    print("Unique File Extents Extents added ontop Extents added    ontop")
    print("per       subvolume of older  subvolume of current(act) subvolume")
    print("-------------------|-------------------|----------------------")
    print("SubvolumId     Size SubvolumId     Size SubvolumId     Size")
    #next_snapshot is actually the older snapshot
    for index,snapshot in enumerate(subvolume_list):
        previous_snapshot = subvolume_list[index-1]
        if index==0:
            previous_snapshot = None
            current_snashot=snapshot
        try:
            next_snapshot = subvolume_list[index+1]
        except:
            next_snapshot = None
        #print(index,snapshot,previous_snapshot,next_snapshot)
        if previous_snapshot != None and next_snapshot != None :
            diff_older_snapshot=snapshot - next_snapshot
            unique_snapshot=diff_older_snapshot-previous_snapshot
            diff_newer_snapshot=snapshot-current_snashot
        elif previous_snapshot == None:
            diff_older_snapshot = unique_snapshot = snapshot - next_snapshot
            diff_newer_snapshot=snapshot
        else:
            diff_older_snapshot=snapshot
            diff_newer_snapshot=snapshot-current_snashot
            unique_snapshot=diff_older_snapshot-previous_snapshot
        print(unique_snapshot,diff_older_snapshot,diff_newer_snapshot)
