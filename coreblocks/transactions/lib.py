from amaranth import *
from .core import *
from .core import DebugSignals
from ._utils import _coerce_layout, MethodLayout

__all__ = [
    "FIFO",
    "ClickIn",
    "ClickOut",
    "AdapterTrans",
    "Adapter",
    "ConnectTrans",
    "CatTrans",
    "ManyToOneConnectTrans",
]

# FIFOs

import amaranth.lib.fifo


class FIFO(Elaboratable):
    def __init__(self, layout, depth, fifoType=amaranth.lib.fifo.SyncFIFO):
        layout = _coerce_layout(layout)
        self.width = len(Record(layout))
        self.depth = depth
        self.fifoType = fifoType

        self.read = Method(o=layout)
        self.write = Method(i=layout)

    def elaborate(self, platform):
        m = Module()

        m.submodules.fifo = fifo = self.fifoType(width=self.width, depth=self.depth)

        assert fifo.fwft  # the read method requires FWFT behavior

        @def_method(m, self.write, ready=fifo.w_rdy)
        def _(arg):
            m.d.comb += fifo.w_en.eq(1)
            m.d.comb += fifo.w_data.eq(arg)

        @def_method(m, self.read, ready=fifo.r_rdy)
        def _(arg):
            m.d.comb += fifo.r_en.eq(1)
            return fifo.r_data

        return m


# "Clicked" input


class ClickIn(Elaboratable):
    def __init__(self, layout: MethodLayout = 1):
        self.get = Method(o=layout)
        self.btn = Signal()
        self.dat = Record(_coerce_layout(layout))

    def elaborate(self, platform):
        m = Module()

        btn1 = Signal()
        btn2 = Signal()
        dat1 = Signal.like(self.dat)
        m.d.sync += btn1.eq(self.btn)
        m.d.sync += btn2.eq(btn1)
        m.d.sync += dat1.eq(self.dat)
        get_ready = Signal()
        get_data = Signal.like(self.dat)

        @def_method(m, self.get, ready=get_ready)
        def _(arg):
            m.d.sync += get_ready.eq(0)
            return get_data

        with m.If(~btn2 & btn1):
            m.d.sync += get_ready.eq(1)
            m.d.sync += get_data.eq(dat1)

        return m


# "Clicked" output


class ClickOut(Elaboratable):
    def __init__(self, layout: MethodLayout = 1):
        self.put = Method(i=layout)
        self.btn = Signal()
        self.dat = Record(_coerce_layout(layout))

    def elaborate(self, platform):
        m = Module()

        btn1 = Signal()
        btn2 = Signal()
        m.d.sync += btn1.eq(self.btn)
        m.d.sync += btn2.eq(btn1)

        @def_method(m, self.put, ready=~btn2 & btn1)
        def _(arg):
            m.d.sync += self.dat.eq(arg)

        return m


# Testbench-friendly input/output


class AdapterBase(Elaboratable):
    def __init__(self, iface: Method):
        self.iface = iface
        self.en = Signal()
        self.done = Signal()

    def debug_signals(self) -> DebugSignals:
        return [self.en, self.done, self.data_in, self.data_out]


class AdapterTrans(AdapterBase):
    def __init__(self, iface: Method):
        super().__init__(iface)
        self.data_in = Record.like(iface.data_in)
        self.data_out = Record.like(iface.data_out)

    def elaborate(self, platform):
        m = Module()

        # this forces data_in signal to appear in VCD dumps
        data_in = Signal.like(self.data_in)
        m.d.comb += data_in.eq(self.data_in)

        with Transaction().body(m, request=self.en):
            data_out = self.iface(m, arg=data_in)
            m.d.comb += self.data_out.eq(data_out)
            m.d.comb += self.done.eq(1)

        return m


class Adapter(AdapterBase):
    def __init__(self, *, i: MethodLayout = 0, o: MethodLayout = 0):
        super().__init__(Method(i=i, o=o))
        self.data_in = Record.like(self.iface.data_out)
        self.data_out = Record.like(self.iface.data_in)

    def elaborate(self, platform):
        m = Module()

        # this forces data_in signal to appear in VCD dumps
        data_in = Signal.like(self.data_in)
        m.d.comb += data_in.eq(self.data_in)

        @def_method(m, self.iface, ready=self.en)
        def _(arg):
            m.d.comb += self.data_out.eq(arg)
            m.d.comb += self.done.eq(1)
            return data_in

        return m


# Example transactions


class ConnectTrans(Elaboratable):
    def __init__(self, method1: Method, method2: Method):
        self.method1 = method1
        self.method2 = method2

    def elaborate(self, platform):
        m = Module()

        with Transaction().body(m):
            data1 = Record.like(self.method1.data_out)
            data2 = Record.like(self.method2.data_out)

            m.d.comb += data1.eq(self.method1(m, data2))
            m.d.comb += data2.eq(self.method2(m, data1))

        return m


class ManyToOneConnectTrans(Elaboratable):
    def __init__(self, *, get_results: list[Method], put_result: Method):
        self.get_results = get_results
        self.m_put_result = put_result

        self.count = len(self.get_results)

    def elaborate(self, platfrom):
        m = Module()

        for i in range(self.count):
            setattr(
                m.submodules, f"ManyToOneConnectTrans_input_{i}", ConnectTrans(self.m_put_result, self.get_results[i])
            )

        return m


class CatTrans(Elaboratable):
    def __init__(self, src1: Method, src2: Method, dst: Method):
        self.src1 = src1
        self.src2 = src2
        self.dst = dst

    def elaborate(self, platform):
        m = Module()

        with Transaction().body(m):
            sdata1 = self.src1(m)
            sdata2 = self.src2(m)
            ddata = Record.like(self.dst.data_in)
            self.dst(m, ddata)

            m.d.comb += ddata.eq(Cat(sdata1, sdata2))

        return m
