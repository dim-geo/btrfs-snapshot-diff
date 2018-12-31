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
import argparse
import sys
from collections import deque
from collections import Counter

#Class to hold data. It's a dictionary of dictionaries.
#tree[key of the extent]= {range1: [snapshots],range2: [snapshots]}

class TreeWrapper:
    def __init__(self):
        self._tree=dict()
        self._snapshots=[]
    
    #unfortunately some extents reappear, maybe there are dedup or reflink?
    #right know they are completely ignored
    def add(self,tree,key,start,stop):
                  if key in self._tree.keys():
                      #data_tree[key].update([datum.offset,stop])
                      add=True
                      ranges=sorted(self._tree[key].keys())
                      for limit in ranges:
                          if limit > stop:
                              break
                          snapshots=self._tree[key][limit]
                          if limit == start or limit == stop:
                              if tree in snapshots:
                                  add=False
                                  #print(tree,key,start,stop)
                                  #print(sorted(self._tree[key].items()))
                                  break
                      if add:
                          if start in self._tree[key].keys():
                              self._tree[key][start].append(tree)
                          else:
                              self._tree[key][start]=[tree]
                          if stop in self._tree[key].keys():
                              self._tree[key][stop].append(tree)
                          else:
                              self._tree[key][stop]=[tree]
                  else:
                      #data_tree[key]=sortedcontainers.SortedSet([datum.offset,stop])
                      #self._tree[key]=sortedcontainers.SortedDict()
                      self._tree[key]=dict()
                      self._tree[key][start]=[tree]
                      self._tree[key][stop]=[tree]

    #each range marker should have only the snapshots that cover the upcoming range
    def transform(self):
        list_of_extents=sorted(self._tree.keys())
        i=0
        while i < len(list_of_extents):
            extent=list_of_extents[i]
            rangedict=self._tree[extent]
            #iterableview = rangedict.items()
            list_of_ranges=sorted(rangedict.keys())
            for j,myrange in enumerate(list_of_ranges):
                if j ==0:
                    continue
                #myrange,myset=mytuple
                myset=set(rangedict[myrange])
                result = set(rangedict[list_of_ranges[j-1]])^myset
                rangedict[myrange]=list(result)
            self._tree[extent]=rangedict
            i+=1

    #return the sum of all data. It should be almost the same as the real data
    #used by the filesystem excluding metadata
    def __len__(self):
        result=0
        for extent,rangedict in self._tree.items():
            iterableview = sorted(rangedict.items())
            for i,mytuple in enumerate(iterableview):
                myrange,myset=mytuple
                #myset=list(myset)
                if len(myset)>=1:
                    try:
                        size=iterableview[i+1][0]-myrange
                        result+=size
                    except:
                        print(extent,sorted(rangedict.items()),mytuple)
        return result

    #find those ranges that have only one snapshot, if this snapshot is deleted
    #this space will be freed
    def find_unique(self):
        result=Counter()
        for extent,rangedict in self._tree.items():
            iterableview = sorted(rangedict.items())
            for i,mytuple in enumerate(iterableview):
                myrange,myset=mytuple
                #myset=list(myset)
                if len(myset)==1:
                    try:
                        size=iterableview[i+1][0]-myrange
                        result[myset[0]]+=size
                    except:
                        print(extent,rangedict,mytuple)
        return result
    
    #helper function to find the size of the ranges that have the desired snapshots
    def find_snapshots_size(self,wanted,not_wanted):
        result=0
        for extent,rangedict in self._tree.items():
            rangelist = sorted(rangedict.keys())
            for i,myrange in enumerate(rangelist):
                snapshots=set(rangedict[myrange])
                if len(set(wanted) & snapshots)>0 and len(set(not_wanted) & snapshots) ==0:
                    try:
                        result+=rangelist[i+1]-myrange
                    except:
                        print(wanted,not_wanted)
                        print(extent,sorted(rangedict.items()),myrange)
        return result
    
    def add_snapshots(self,snapshots):
        self._snapshots=snapshots.copy()
    
    #calculate the size of ranges ontop of the previous subvolume
    def find_snapshot_size_to_previous(self):
        results=Counter()
        for i, snapshot in enumerate(self._snapshots):
                if i>0:
                    results[snapshot]+=self.find_snapshots_size([snapshot],[self._snapshots[i-1]])
                else:
                    results[snapshot]+=self.find_snapshots_size([snapshot],[])
        return results

    #calculate the size of ranges ontop of the current active subvolume
    def find_snapshot_size_to_current(self):
        results=Counter()
        current=self._snapshots[-1]
        for snapshot in self._snapshots:
                if snapshot == current:
                    results[snapshot]+=self.find_snapshots_size([snapshot],[])
                else:
                    results[snapshot]+=self.find_snapshots_size([snapshot],[current])
        return results


def disk_parse(data_tree,fs,tree):
          print(tree)
          for header, data in btrfs.ioctl.search_v2(fs.fd, tree):
            if header.type == btrfs.ctree.EXTENT_DATA_KEY:
              datum=btrfs.ctree.FileExtentItem(header,data)
              if datum.type != btrfs.ctree.FILE_EXTENT_INLINE:# and datum.disk_bytenr !=0:
                  key=(datum.disk_bytenr,datum.disk_num_bytes)
                  stop=datum.offset+datum.num_bytes
                  data_tree.add(tree,key,datum.offset,stop)


def main(): 
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=str,
                    help="path of the btrfs filesystem")
    parser.add_argument("-r", "--root", type=int,default=5,
                    help="current active subvolume to analyze, default is 5")
    parser.add_argument('subs', nargs='*', type=int, help='Ignore these subvolumes')
    args=parser.parse_args()
    #list of ignored subvolumes
    ignored_trees=set(args.subs)
    ignored_trees.add(args.root)
    fs = btrfs.FileSystem(args.path)
    
    #data_tree=sortedcontainers.SortedDict()
    #data_tree=dict()
    data_tree=TreeWrapper()
    #data_tree=TreeWrapperSql()
    #data_tree=TreeWrapperCompress()
    snapshots=[]

    disk_parse(data_tree,fs,args.root)
    snapshots.append(args.root)
    
    for subvol in fs.subvolumes():
        tree = subvol.key.objectid
        if tree not in ignored_trees:
          disk_parse(data_tree,fs,tree)
          snapshots.append(tree)
    changed_snapshots = deque(snapshots)
    changed_snapshots.rotate(-1)
    data_tree.add_snapshots(list(changed_snapshots))
    data_tree.transform()
    unique_sum=0
    unique_data=data_tree.find_unique()
    current_data=data_tree.find_snapshot_size_to_current()
    previous_data=data_tree.find_snapshot_size_to_previous()
    print(" Unique File Extents  Extents added ontop   Extents added ontop of")
    print(" per       subvolume  of previous subvolume current(act) subvolume")
    print("---------------------|---------------------|----------------------")
    print("SubvolumId       Size                  Size                   Size")
    for snapshot in reversed(changed_snapshots):
        print("{:>10} {:>10}            {:>10}             {:>10}".format(snapshot,btrfs.utils.pretty_size(unique_data[snapshot]),btrfs.utils.pretty_size(previous_data[snapshot]),btrfs.utils.pretty_size(current_data[snapshot])))
        unique_sum+=unique_data[snapshot]
    print("Size/Cost of snapshots:",btrfs.utils.pretty_size(unique_sum),"Volatility:","{:.2%}".format(unique_sum/len(data_tree)))


if __name__ == '__main__':
    main()
