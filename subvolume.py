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
from collections import defaultdict
import math, array
from functools import lru_cache

#function to convert a pair of positive integers to a single integer
#we want to decrease memory consumption, thus we need this trick
#http://szudzik.com/ElegantPairing.pdf
#cache the results for speed up

@lru_cache(maxsize=32)
def unique_number(x,y):
    result=x
    if x >=y:
        result+=y
        result+=x**2
    else:
        result+=y**2
    return result

#undo the above function, return x,y based on a single number
#also cache the results

@lru_cache(maxsize=131072)
def unique_to_pair(number):
        root=int(math.floor(math.sqrt(number)))
        crit=number-root**2
        if crit< root:
                x=crit
                y=root
        else:
                x=root
                y=crit-root
        return x,y

#take a list of 'paired' numbers and return the x coordinate, which is snapshot
#stored into the pair
def return_snapshots(mylist):
        result=[]
        for item in mylist:
                snapshot,_=unique_to_pair(item)
                result.append(snapshot)
        return result

#take a list of 'paired' numbers and return the paired number that has the same
#x coordinate, which is the snapshot stored into the pair
def return_coded(mylist,snapshot):
    for item in mylist:
        snapshot_pair,_=unique_to_pair(item)
        if snapshot_pair == snapshot:
            return item
    return None

#take a paired number and compare it with a snapshot
#cache the results for speedup
@lru_cache(maxsize=131072)
def compare_pair_to_snapshot(item,snapshot):
        snapshot_pair,_=unique_to_pair(item)
        if snapshot_pair == snapshot:
            return True
        return False

#Class to hold data. It's a dictionary of dictionaries.
#tree[key of the extent]= {range1: [list of paired (snapshot,inode)],range2: [list of paired (snapshot,inode)]}
#inodes data are used to find which files hold data of unique extents.
class TreeWrapper:
    def __init__(self):
        self._tree=dict()
        self._snapshots=[]
    
    #unfortunately some extents reappear, maybe there are dedup or reflink?
    #right know they are completely ignored
        
    #check if the current tree has data for this extent/key.
    #if it has, check if the current extent range is already parsed.
        
    #use array instead of list because integers consume too much memory in python
    def add(self,tree,key,start,stop,inode):
                  mypair=unique_number(tree,inode)
                  if key in self._tree.keys():
                      add=True
                      ranges=sorted(self._tree[key].keys())
                      for limit in ranges:
                          if limit > stop:
                              break
                          #this code need to be reworked to cover when extents are adjucent
                          #for the same snapshot
                          if limit == start or limit == stop:
                              #since snapshots are parsed linearly, check only if
                              #the last data are from the same snapshot
                              if compare_pair_to_snapshot(self._tree[key][limit][-1],tree):
                                  add=False
                                  break
                      if add:
                          if start in self._tree[key].keys():
                              self._tree[key][start].append(mypair)
                          else:
                              self._tree[key][start]=array.array('Q')
                              self._tree[key][start].append(mypair)
                          if stop in self._tree[key].keys():
                              self._tree[key][stop].append(mypair)
                          else:
                              self._tree[key][stop]=array.array('Q')
                              self._tree[key][stop].append(mypair)
                  else:
                      self._tree[key]=dict()
                      self._tree[key][start]=array.array('Q')
                      self._tree[key][start].append(mypair)
                      self._tree[key][stop]=array.array('Q')
                      self._tree[key][stop].append(mypair)

    #this function analyzes the tree after all data are added.
    #for each range find which subvolumes use that range.
    #each snapshot has added its start and stop.
    #we keep the snapshots only in the start part.
    #scenario before: extent1:  pos_1[tree1]..........pos_2[tree2]....pos_3[tree2]...pos_4[tree1]
    #final result: pos_1[tree1]..........pos_2[tree1,tree2]....pos_3[tree1]...pos_4[]
    def transform(self):
        list_of_extents=sorted(self._tree.keys())
        i=0
        while i < len(list_of_extents):
            extent=list_of_extents[i]
            rangedict=self._tree[extent]
            list_of_ranges=sorted(rangedict.keys())
            for j,myrange in enumerate(list_of_ranges):
                if j ==0:
                    continue
                #the upcoming extent is used by the snapshots symmetrical difference of set of snapshots
                myset=set(return_snapshots(rangedict[myrange]))
                result = set(return_snapshots(rangedict[list_of_ranges[j-1]]))^myset
                #again store the ressult in array, not list.
                subvol_list=array.array('Q')
                for subvol in result:
                    data= return_coded(rangedict[myrange],subvol)
                    if data ==None:
                        data=return_coded(rangedict[list_of_ranges[j-1]],subvol)
                    if data ==None:
                        print("problem!",data,subvol)
                    subvol_list.append(data)
                rangedict[myrange]=subvol_list
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
    #this space will be freed.
    #based on the scenario of transform is should return:
    #result[tree1]=pos2-pos1+pos4-pos3
    #result[tree2]=0
    #if files are analyzed use the inode data to find them ans store them in different dictionary.
    def find_unique(self,fs,analyze_file):
        result=Counter()
        result_data=defaultdict(set)
        for extent,rangedict in self._tree.items():
            iterableview = sorted(rangedict.items())
            for i,mytuple in enumerate(iterableview):
                myrange,unique_pair_list=mytuple
                #myset=list(myset)
                if len(unique_pair_list)==1:
                    subvolume,inode=unique_to_pair(unique_pair_list[0])
                    size=iterableview[i+1][0]-myrange
                    result[subvolume]+=size
                    #result[myset[0]]+=size
                    #print(inode)
                    if analyze_file:
                        try:
                            file=btrfs.ioctl.ino_lookup(fs.fd,subvolume,inode)
                            result_data[file.name_bytes.decode('utf-8')].add(subvolume)
                        except:
                            print("Inode not found",inode)
        return result,result_data

    #helper function to find the size of the extend ranges that have the desired snapshots
    def find_snapshots_size(self,wanted,not_wanted):
        result=0
        for extent,rangedict in self._tree.items():
            rangelist = sorted(rangedict.keys())
            for i,myrange in enumerate(rangelist):
                snapshots=set(return_snapshots(rangedict[myrange]))
                if len(set(wanted) & snapshots)>0 and len(set(not_wanted) & snapshots) ==0:
                    try:
                        result+=rangelist[i+1]-myrange
                    except:
                        print(wanted,not_wanted)
                        print(extent,sorted(rangedict.items()),myrange)
        return result
    
    #the active subvolume must be the last one
    def add_snapshots(self,snapshots):
        self._snapshots=snapshots.copy()
    
    #calculate the size of ranges ontop of the previous subvolume
    #older subvolumes must be first in subvolume list
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

#main function to parse data from disk and add the to the tree of extents
def disk_parse(data_tree,fs,tree):
          print("Parsing subvolume:",tree)
          min_key=btrfs.ctree.Key(0,btrfs.ctree.EXTENT_DATA_KEY,0)
          for header, data in btrfs.ioctl.search_v2(fs.fd, tree,min_key):
            if header.type == btrfs.ctree.EXTENT_DATA_KEY:
              datum=btrfs.ctree.FileExtentItem(header,data)
              if datum.type != btrfs.ctree.FILE_EXTENT_INLINE:# and datum.disk_bytenr !=0:
                  key=(datum.disk_bytenr,datum.disk_num_bytes)
                  stop=datum.offset+datum.num_bytes
                  data_tree.add(tree,key,datum.offset,stop,datum.key.objectid)
                  

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-u","--unique",action='store_true',help="calculate only unique data, -r argument makes no sense if -u is active")
    parser.add_argument("-f","--files",action='store_true',help="find filenames that exist in unique extents")
    parser.add_argument("path", type=str,
                    help="path of the btrfs filesystem")
    parser.add_argument("-r", "--root", type=int,default=5,
                    help="current active subvolume to analyze first, default is 5")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-i', '--ignore', action='store_true',help="Do not analyze the specified subvolumes")
    group.add_argument('-o', '--only', action='store_true',help="Analyze only the specified subvolumes")
    parser.add_argument('subvolume', nargs='*', type=int, help='Subvolumes to ingore or analyze')
    args=parser.parse_args()

    #find subvolumes to parse, make sure -r subvolume stays first
    parse_trees=[5]
    if args.root!=5:
        parse_trees=[args.root,5]
    fs = btrfs.FileSystem(args.path)
    for subvol in fs.subvolumes():
        if subvol.key.objectid != args.root:
            parse_trees.append(subvol.key.objectid)

    #these are the subvolumes specified by the user, these will be either ignored
    #or all the other subvolumes will be ingored
    special_subvolumes=set(args.subvolume)
    
    #if no argument specified then assume that the user wanted to ingore the speficied subvolumes
    if args.ignore == False and args.only== False:
        args.ignore=True
    
    #remove the unneeded subvolumes
    if args.ignore:    
        for item in special_subvolumes:
            try:
                parse_trees.remove(item)
            except:
                pass
    else:
        for tree in parse_trees[:]:
            if tree not in special_subvolumes:
                parse_trees.remove(tree)
    
    data_tree=TreeWrapper()
    
    #move the root subvolume in the end
    #older subvolumes must be first
    changed_snapshots = deque(parse_trees)
    changed_snapshots.rotate(-1)
    parse_trees=list(changed_snapshots)
    data_tree.add_snapshots(parse_trees)
    
    #parse the trees from newer to older
    parse_trees=list(reversed(parse_trees))
    print("Subvolumes to parse:",parse_trees)
    for tree in parse_trees:
        disk_parse(data_tree,fs,tree)

    data_tree.transform()
    #print(unique_number.cache_info())
    #print(unique_to_pair.cache_info())
    #print(compare_pair_to_snapshot.cache_info())
    unique_sum=0
    unique_data,files=data_tree.find_unique(fs,args.files)
    #if unique analysis is only needed, do not calculate differences 
    if args.unique:
      current_data=Counter()
      previous_data=Counter()
    else:
      current_data=data_tree.find_snapshot_size_to_current()
      previous_data=data_tree.find_snapshot_size_to_previous()
    print(" Unique File Extents  Extents added ontop   Extents added ontop of")
    print(" per       subvolume  of previous subvolume current(act) subvolume")
    print("---------------------|---------------------|----------------------")
    print("SubvolumId       Size                  Size                   Size")
    for snapshot in parse_trees:
        print("{:>10} {:>10}            {:>10}             {:>10}".format(snapshot,btrfs.utils.pretty_size(unique_data[snapshot]),btrfs.utils.pretty_size(previous_data[snapshot]),btrfs.utils.pretty_size(current_data[snapshot])))
        #print(files[snapshot])
        unique_sum+=unique_data[snapshot]
    print("Size/Cost of subvolumes:",btrfs.utils.pretty_size(unique_sum),"Volatility:","{:.2%}".format(unique_sum/len(data_tree)))
    if args.files:
        print()
        print("Possible Unique Files:")
        for file,myset in files.items():
            print(file,":",myset)

if __name__ == '__main__':
    main()
