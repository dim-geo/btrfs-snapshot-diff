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
import copy
import bisect
import lzma
import pickle
import argparse
import time

#function to calculate the difference between 2 ranges

def range_sub(range1,range2):
    result=[]
    a,b=range1
    x,y=range2
    if x>b or y<a:
        result.append(range1)
        return result
    if y>=b:
        if x>a:
            b=x-1
        else:
            return result
    else:
        if x>a:
            result.append((a,x-1))
        a=y+1
    result.append((a,b))
    return result

#helper function for subtraction parallelism

def subtract(pair):
    a,b=pair
    if b != None:
        a-=b
    return a

def subtract_new_obj(pair):
    a,b=pair
    x=a-b
    return x


#Normal File extent class
#Data Address + a list of ranges

class MyFileExtent:
    def __init__(self,address1,address2,start,size):
        self._address=(address1,address2)
        if size>0:
            self._ranges=[(start,start+size-1)]
        else:
            self._ranges=[]
        #self._start=start
        #self._size=size

    #Calculate difference between extents.
    #Extents with the same address require special manipulation
    #in reality we need to perform range operations

    def __sub__(self,other):
        if self._address != other._address:
            return copy.deepcopy(self)
        else:            
            new = copy.deepcopy(self)
            i=0
            j=0 # j=bisect.bisect_left(other._ranges,new_ranges[0])
            while(i<len(new._ranges) and j < len(other._ranges)):
                myrange=new._ranges[i]
                rang=other._ranges[j]
                results=range_sub(myrange,rang)
                if len(results) == 0:
                    del new._ranges[i]
                if len(results) >0 and results[0] != myrange:
                    del new._ranges[i]
                    k=i
                    for result in results:
                        new._ranges.insert(k,result)
                        k+=1
                #print(i,j,len(new._ranges),len(other._ranges[j]))
                #print(new._ranges[i],other._ranges[j])
                if i>=len(new._ranges):
                    break
                k=i
                l=j
                if new._ranges[k][1]< other._ranges[l][1]:
                    i+=1
                if new._ranges[k][0]>other._ranges[l][1]:
                    j+=1
            return new


    #both of these are not accurate when both extents have the same address!
    def __lt__(self,other):
        if self._address < other._address:
            return True
        else:
            return False

    def __le__(self,other):
        if self._address <= other._address:
            return True
        else:
            return False
    
    #check if two extents have the same address, used in subtraction and merging
    def same_address(self,other):
        if self._address != other._address:
            return False
        else:
            return True
    
    #merge 2 extents if they have the same address. In reality mergesort would be
    #better, however the other extent is always one range
    def merge(self,other):
        if self._address == other._address:
            for item in other._ranges:
                bisect.insort(self._ranges,item)
        return self

    #calculate the byte size of the extent
    def __len__(self):
        size=0
        for rang in self._ranges:
            start,stop=rang
            size+=(stop-start+1)
        return size
    
    #convert to string, show all data
    def __str__(self):
        return "{} {}".format(self._address,self._ranges)

#class to represent subvolume/snapshot. It has a unique id and a list of extents
class Snapshot:
    def __init__(self, objectid):
        self._objectid = objectid
        #self._blocks=SortedList()
        self._blocks=[]
        self._dummyi=0
        #self._fileextents=[]
    
    #add an extent in this snapshot, how it can be made faster?
    #we want the extents sorted & merged
    def add(self,offset1,offset2,offset3,size):
        newextent=MyFileExtent(offset1,offset2,offset3,size)
        #implement insertsort and merging
        i=bisect.bisect_left(self._blocks,newextent)
        if i< len(self._blocks) and newextent.same_address(self._blocks[i]):
            self._blocks[i].merge(newextent)
        else:
            self._blocks.insert(i,newextent)
    
    #make an iterator to facilitate subtraction
    #each tuple contains an extent with the same address extent of other
    #if it does not exist, put none
    def _sub_list_generator(self,other):
        i=j=0
        while(i<len(self._blocks)):
            #print(i,j)
            if j==len(other._blocks) or self._blocks[i]< other._blocks[j]:
                yield((copy.deepcopy(self._blocks[i]),None))
                i+=1
            elif self._blocks[i].same_address(other._blocks[j]):
                yield((copy.deepcopy(self._blocks[i]),other._blocks[j]))
                i+=1
                j+=1
            else:
                j+=1
    
    #Parallelize subtraction of snapshots
    def __oldsub__(self,other):
        newsnapshot=Snapshot(self._objectid)
        chunk=len(self._blocks)//multiprocessing.cpu_count()
        with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
            extentgenerator=pool.imap(subtract,self._sub_list_generator(other),chunk)
            for extent in extentgenerator:
                newsnapshot._blocks.append(extent)
        return newsnapshot


    #serial subtraction of snapshots
    def __sub__(self,other):
        newsnapshot=Snapshot(self._objectid)
        i=0
        for extent in self._blocks:
            newextent=copy.deepcopy(extent)
            while(i < len(other._blocks) and other._blocks[i]<=extent):
                if newextent.same_address(other._blocks[i]):
                    newextent-=other._blocks[i]
                i+=1
            if len(newextent)!=0:
                newsnapshot._blocks.append(newextent)
        return newsnapshot

    def __len__(self):
        size=0
        for extent in self._blocks:
            #print(extent)
            size+=len(extent)
        return size

    def __str__(self):
        return '{:>10} {:>10}'.format(self._objectid,btrfs.utils.pretty_size(len(self)))

#helper function to create snapshots in parallel
#compress snapshots as they can take huge amounts of ram
def find_extents(pair):
  fs,tree = pair
  snapshot=Snapshot(tree)
  #print("Start",tree)
  #search in this subvolume all file extents
  for header, data in btrfs.ioctl.search_v2(fs.fd, tree):
    if header.type == btrfs.ctree.EXTENT_DATA_KEY:
      datum=btrfs.ctree.FileExtentItem(header,data)
      #print(datum)
      #ignore inline file extents, they are small
      #btrfs.utils.pretty_print(datum)
      if datum.type != btrfs.ctree.FILE_EXTENT_INLINE and datum.disk_bytenr !=0:
        snapshot.add(datum.disk_bytenr,datum.disk_num_bytes,datum.offset,datum.num_bytes)
  #snapshot.compact()
  #print("Compress",tree)
  compressed_snapshot=lzma.compress(pickle.dumps(snapshot))
  #print("Done",tree)
  #return snapshot
  return compressed_snapshot


if __name__ == "__main__":

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
    subvolume_list=[]
    #iterate all subvolumes
    arguments=[]
    for subvol in fs.subvolumes():
        tree = subvol.key.objectid
        if tree not in ignored_trees:
            arguments.append((fs,tree))
    arguments.append((fs,args.root))
    
    chunk=len(arguments)//multiprocessing.cpu_count()
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        subvolume_list=pool.map(find_extents,arguments,chunk)

    #make sure that subvolume order is from newest (current) to oldest

    subvolume_list.reverse()
    
    #parse list of subvolumes and calculate the number of the unique file extents in this subvolume
    #calculate also how much data were changed, compared to the older subvolume
    print(" Unique File Extents  Extents added ontop   Extents added ontop of")
    print(" per       subvolume  of previous subvolume current(act) subvolume")
    print("---------------------|---------------------|------------------------")
    print("SubvolumId       Size SubvolumId       Size SubvolumId       Size")
    #next_snapshot is actually the older snapshot
    size=0
    snappy=current_snashot=pickle.loads(lzma.decompress(subvolume_list[0]))
    first_size=len(current_snashot)
    #old_snap=None
    i=0
    while i< len(subvolume_list):
        #snappy=pickle.loads(lzma.decompress(snapshot))
        #start = time.time()
        if i==0:
            previous_snapshot = None
        try:
            next_snapshot = pickle.loads(lzma.decompress(subvolume_list[i+1]))
        except:
            next_snapshot = None
        #print(index,snapshot,previous_snapshot,next_snapshot)
        if previous_snapshot != None and next_snapshot != None :
            #diff_older_snapshot=snappy - next_snapshot
            #diff_newer_snapshot=snappy - current_snashot
            arguments=[(snappy,next_snapshot),(snappy,current_snashot)]
            with multiprocessing.Pool(processes=2) as pool:
                diff_older_snapshot,diff_newer_snapshot=pool.map(subtract,arguments)
            unique_snapshot=diff_older_snapshot-previous_snapshot
        elif previous_snapshot == None:
            diff_older_snapshot = unique_snapshot = snappy - next_snapshot
            diff_newer_snapshot=snappy
        else:
            diff_older_snapshot=snappy
            arguments=[(snappy,current_snashot),(snappy,previous_snapshot)]
            with multiprocessing.Pool(processes=2) as pool:
                diff_newer_snapshot,unique_snapshot=pool.map(subtract,arguments)
            #diff_newer_snapshot=snappy-current_snashot
            #unique_snapshot=snappy-previous_snapshot
        #print(f"{i} took {time.time() - start:.2f} seconds")
        size+=len(unique_snapshot)
        print(unique_snapshot,diff_older_snapshot,diff_newer_snapshot)
        previous_snapshot=snappy
        snappy=next_snapshot
        i+=1
    print("Size/Cost of snapshots:",btrfs.utils.pretty_size(size),"Volatility:","{:.2%}".format(size/first_size))
