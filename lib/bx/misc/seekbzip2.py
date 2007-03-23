import os
import bisect
import sys
    
from _seekbzip2 import SeekBzip2
    
class SeekableBzip2File( object ):
    
    def __init__( self, filename, table_filename, **kwargs ):
        self.filename = filename
        self.table_filename = table_filename
        self.init_table()
        self.init_bz2()
        self.pos = 0
        self.dirty = True
        
    def init_bz2( self ):
        self.seek_bz2 = SeekBzip2( self.filename )
        
    def init_table( self ):
        # Position in plaintext file
        self.table_positions = []
        # Position of corresponding block in bz2 file (bits)
        self.table_bz2positions = []
        pos = 0
        for line in open( self.table_filename ):
            fields = line.split()
            # Position of the compressed block in the bz2 file
            bz2_pos = int( fields[0] )
            # Length of the block when uncompressed
            length = int( fields[1] )
            self.table_positions.append( pos )
            self.table_bz2positions.append( bz2_pos )
            pos = pos + length
        self.size = pos
        
    def fix_dirty( self ):
        # Our virtual position in the uncompressed data is out of sync
        # FIXME: If we're moving to a later position that is still in 
        # the same block, we could just read and throw out bytes in the
        # compressed stream, less wasteful then backtracking
        chunk, offset = self.get_chunk_and_offset( self.pos )
        # Get the seek position for that chunk and seek to it
        bz2_seek_pos = self.table_bz2positions[chunk] 
        self.seek_bz2.seek( bz2_seek_pos )
        # Consume bytes to move to the correct position
        assert len( self.seek_bz2.read( offset ) ) == offset
        # Update state
        self.dirty = False
        
    def read( self, sizehint=-1 ):
        if sizehint < 0:
            chunks = []
            while 1:
                self._read( 1024*1024 )
                if val:
                    chunks.append( val )
                else:
                    break
            return "".join( chunks )
        else:
            return self._read( sizehint )
        
    def _read( self, size ):
        if self.dirty: self.fix_dirty()
        val = self.seek_bz2.read( size )
        if val is None:
            # EOF
            self.pos = self.size
            val = ""
        else:
            self.pos = self.pos + len( val )
        return val
        
    def readline( self, size=-1 ):
        if self.dirty: self.fix_dirty()
        val = self.seek_bz2.readline( size )
        if val is None:
            # EOF
            self.pos = self.size
            val = ""
        else:
            self.pos = self.pos + len( val )
        return val
        
    def tell( self ):
        return self.pos
            
    def get_chunk_and_offset( self, position ):
        # Find the chunk that position is in using a binary search
        chunk = bisect.bisect( self.table_positions, position ) - 1
        offset = position - self.table_positions[chunk]
        return chunk, offset
        
    def seek( self, offset, whence=0 ):
        # Determine absolute target position
        if whence == 0:
            target_pos = offset
        elif whence == 1:
            target_pos = self.pos + offset
        elif whence == 2:
            target_pos = self.size - offset
        else:
            raise Exception( "Invalid `whence` argument: %r", whence )
        # Check if this is a noop
        if target_pos == self.pos:
            return    
        # Verify it is valid
        assert 0 <= target_pos < self.size, "Attempt to seek outside file"
        # Move the position
        self.pos = target_pos
        # Mark as dirty, the next time a read is done we need to actually
        # move the position in the bzip2 file
        self.dirty = True
        
    # ---- File like methods ------------------------------------------------
    
    def next(self):
        ln = self.readline()
        if ln == "":
            raise StopIteration()
        return ln
    
    def __iter__(self):
        return self
        
    def readlines(self,sizehint=-1):
        return [ln for ln in self]

    def xreadlines(self):
        return iter(self)