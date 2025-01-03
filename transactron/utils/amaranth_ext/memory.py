from amaranth import *
from amaranth.utils import *
import amaranth.lib.memory as memory
from amaranth.hdl import AlreadyElaborated

from typing import Optional, Any, final
from collections.abc import Iterable

from .. import get_src_loc
from amaranth_types.types import ShapeLike, ValueLike

__all__ = ["MultiReadMemory", "MultiportXORMemory"]

@final
class MultipleWritePorts(Exception):
    """Exception raised when a single write memory is being requested multiple write ports."""

class MultiReadMemory(Elaboratable):
    """Memory with one write and multiple read ports.

    One can request multiple read ports and not more than 1 read port. Module internally
    uses multiple (number of read ports) instances of amaranth.lib.memory.Memory with one 
    read and one write port.

    Attributes
    ----------
    shape: ShapeLike
        Shape of each memory row.
    depth: int
        Number of memory rows.
    """

    def __init__(
        self,
        *,
        shape: ShapeLike,
        depth: int,
        init: Iterable[ValueLike],
        attrs: Optional[dict[str, str]] = None,
        src_loc_at: int = 0
    ):
        """
        Parameters
        ----------
        shape: ShapeLike
            Shape of each memory row.
        depth : int
            Number of memory rows.
        init : iterable of initial values
            Initial values for memory rows.
        src_loc: int 
            How many stack frames deep the source location is taken from.
        """

        self._shape = shape
        self._depth = depth
        self._init = init
        self._attrs = attrs
        self.src_loc = src_loc_at

        self._read_ports: "list[ReadPort]" = []
        self._write_ports: "list[WritePort]" = []
        self._frozen = False

    @property
    def shape(self):
        return self._shape

    @property
    def depth(self):
        return self._depth

    @property
    def init(self):
        return self._init

    @init.setter
    def init(self, init):
        self._init = init

    @property
    def attrs(self):
        return self._attrs
    
    @property
    def read_ports(self):
        """All read ports defined so far.
        """
        return tuple(self._read_ports)

    @property
    def write_ports(self):
        """All write ports defined so far.
        """
        return tuple(self._write_ports)

    def read_port(
        self,
        *,
        domain: str = "sync",
        transparent_for: Iterable[Any] = (),
        src_loc_at: int = 0
    ) :
        if self._frozen:
            raise AlreadyElaborated("Cannot add a memory port to a memory that has already been elaborated")
        return ReadPort(memory=self, width=self.shape, depth=self.depth, init=self.init, transparent_for=transparent_for, src_loc=1 + src_loc_at)

    def write_port(
        self,
        *,
        domain: str = "sync",
        granularity: Optional[int] = None,
        src_loc_at: int = 0
    ) :
        if self._frozen:
            raise AlreadyElaborated("Cannot add a memory port to a memory that has already been elaborated")
        if self.write_ports:
            raise MultipleWritePorts("Cannot add multiple write ports to a single write memory")
        return WritePort(memory=self, width=self.shape, depth=self.depth, init=self.init, granularity=granularity, src_loc=1+src_loc_at)

    def elaborate(self, platform) :
        m = Module()

        self._frozen = True

        if self.write_ports:
            write_port = self.write_ports[0]
            for port in self.read_ports:
                if port is None:
                    raise ValueError("Found None in read ports")
                # for each read port a new single port memory block is generated
                mem = memory.Memory(shape=port.width, depth=self.depth, init=self.init, attrs=self.attrs, src_loc_at=self.src_loc)
                m.submodules += mem
                physical_read_port = mem.read_port(transparent_for=port.transparent_for)
                physical_write_port = mem.write_port()
                m.d.comb += [physical_read_port.addr.eq(port.addr),
                             port.data.eq(physical_read_port.data),
                             physical_read_port.en.eq(port.en),
                             physical_write_port.addr.eq(write_port.addr),
                             physical_write_port.data.eq(write_port.data),
                             physical_write_port.en.eq(write_port.en)]
        
        return m


class ReadPort:

    #póki co ignoruję domenę, nie wiem co potem
    def __init__(self, memory, width, depth, init=None, transparent_for=None, src_loc = 0):
        self.src_loc = get_src_loc(src_loc)
        self.depth = depth
        self.width = width
        self.init = init
        self.transparent_for = transparent_for
        self.addr_width = bits_for(self.depth - 1)
        self.en = Signal(1)
        self.addr = Signal(self.addr_width)
        self.data = Signal(width)
        self._memory = memory
        memory._read_ports.append(self)
        
class WritePort:

    #póki co ignoruję domenę i granularity, nie wiem co potem
    def __init__(self, memory, width, depth, init, granularity=None, src_loc = 0):
        self.src_loc = get_src_loc(src_loc)
        self.depth = depth
        self.width = width
        self.init = init
        self.addr_width = bits_for(self.depth - 1)
        self.en = Signal(1)
        self.addr = Signal(self.addr_width)
        self.data = Signal(width)
        self._memory = memory
        memory._write_ports.append(self)

# one mogłyby dziedziczyć po czymś wspólnym, bez sensu identyczne inity
class MultiportXORMemory(Elaboratable):
    """Multiport memory based on xor.

    Multiple read and write ports can be requested. Memory is built of 
    (number of write ports) * (number of write ports - 1 + number of read ports) single port
    memory blocks. XOR is used to enable writing multiple values in one cycle.

    Attributes
    ----------
    shape: ShapeLike
        Shape of each memory row.
    depth: int
        Number of memory rows.
    """

    def __init__(
        self,
        *,
        shape: ShapeLike,
        depth: int,
        init: Iterable[ValueLike],
        attrs: Optional[dict[str, str]] = None,
        src_loc_at: int = 0
    ):
        """
        Parameters
        ----------
        shape: ShapeLike
            Shape of each memory row.
        depth : int
            Number of memory rows.
        init : iterable of initial values
            Initial values for memory rows.
        src_loc: int 
            How many stack frames deep the source location is taken from.
        """

        self._shape = shape
        self._depth = depth
        self._init = init
        self._attrs = attrs
        self.src_loc = src_loc_at

        self._read_ports: "list[ReadPort]" = []
        self._write_ports: "list[WritePort]" = []
        self._frozen = False

    @property
    def shape(self):
        return self._shape

    @property
    def depth(self):
        return self._depth

    @property
    def init(self):
        return self._init

    @init.setter
    def init(self, init):
        self._init = init

    @property
    def attrs(self):
        return self._attrs
    
    @property
    def read_ports(self):
        """All read ports defined so far.
        """
        return tuple(self._read_ports)

    @property
    def write_ports(self):
        """All write ports defined so far.
        """
        return tuple(self._write_ports)
    
    def read_port(
        self,
        *,
        domain: str = "sync",
        transparent_for: Iterable[Any] = (),
        src_loc_at: int = 0
    ) :
        if self._frozen:
            raise AlreadyElaborated("Cannot add a memory port to a memory that has already been elaborated")
        return ReadPort(memory=self, width=self.shape, depth=self.depth, init=self.init, transparent_for=transparent_for, src_loc=1 + src_loc_at)

    def write_port(
        self,
        *,
        domain: str = "sync",
        granularity: Optional[int] = None,
        src_loc_at: int = 0
    ) :
        if self._frozen:
            raise AlreadyElaborated("Cannot add a memory port to a memory that has already been elaborated")
        return WritePort(memory=self, width=self.shape, depth=self.depth, init=self.init, granularity=granularity, src_loc=1+src_loc_at)

    # transparentność trzeba załatwiać osobno, jest opisane w paperze
    def elaborate(self, platform) :
        m = Module()

        self._frozen = True

        addr_width = bits_for(self.depth - 1)

        write_xors: "list[Value]" = [Signal(self.shape) for _ in self.write_ports]
        read_xors: "list[Value]" = [Signal(self.shape) for _ in self.read_ports]
        
        write_regs_addr = [Signal(addr_width) for _ in self.write_ports]
        #sygnał chyba może być też rejestrem
        write_regs_data = [Signal(self.shape) for _ in self.write_ports]

        for index, write_port in enumerate(self.write_ports):
            if write_port is None:
                raise ValueError("Found None in write ports")
            
            index_passed_by = False
            write_xors[index] = write_port.data ^ write_xors[index]
            # muszą zostać dołożone rejestry, żeby zgadzały się timingi przy xor feedback
            for i in range(len(self.write_ports) - 1):
                mem = memory.Memory(shape=self.shape, depth=self.depth, init=self.init, attrs=self.attrs, src_loc_at=self.src_loc)
                mem_name = f"memory_{index}_{i}"
                m.submodules[mem_name] = mem
                physical_read_port = mem.read_port()
                physical_write_port = mem.write_port()

                if i == index:
                    index_passed_by = True
                idx = i+1 if index_passed_by else i
                write_xors[idx] = physical_read_port.data ^ write_xors[idx]

                m.d.comb += [physical_write_port.addr.eq(write_port.addr),
                             physical_write_port.data.eq(write_xors[index]),
                             physical_write_port.en.eq(write_port.en),
                             physical_read_port.en.eq(1),
                             #do sprawdzenia adresy
                             physical_read_port.addr.eq(self.write_ports[idx].addr)]

            read_block = MultiReadMemory(shape=self.shape, depth=self.depth, init=self.init, attrs=self.attrs, src_loc_at=self.src_loc)
            mem_name = f"read_block_{index}"
            m.submodules[mem_name] = read_block
            r_write_port = read_block.write_port()
            r_read_ports = [
                read_block.read_port() for _ in self.read_ports
            ]
            m.d.comb += [r_write_port.addr.eq(write_port.addr),
                         r_write_port.data.eq(write_xors[index]),
                         r_write_port.en.eq(write_port.en)]
            for idx, port in enumerate(r_read_ports):
                read_xors[idx] ^= port.data
                m.d.comb += [port.addr.eq(self.read_ports[idx].addr),
                             port.en.eq(1)]

        for index, port in enumerate(self.read_ports):
            m.d.comb += [port.data.eq(read_xors[index])]

        return m