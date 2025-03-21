from ..structs import SParamFile
from ..bodefano import BodeFano
from ..stabcircle import StabilityCircle
from ..utils import sanitize_filename
from ..citi import CitiWriter

import skrf, math, os
import numpy as np
import fnmatch
import logging
import scipy.signal
import os
import re
from typing import Callable



class SParam:


    plot_fn: "callable[[np.ndarray,np.ndarray,complex,str,str], None]"


    def __init__(self, name: str, f: np.ndarray, s: np.ndarray, z0: float):
        assert len(f) == len(s)
        self.name, self.f, self.s, self.z0 = name, f, s, z0
    

    @staticmethod
    def _adapt_f(a: "SParam", b: "SParam") -> "tuple(skrf.Network)":
        if len(a.f)==len(b.f):
            if all(af==bf for af,bf in zip(a.f, b.f)):
                return a,b
        f_min = max(min(a.f), min(b.f))
        f_max = min(max(a.f), max(b.f))
        f_new = np.array([f for f in a.f if f_min<=f<=f_max])
        freq_new = skrf.Frequency.from_f(f_new, unit='Hz')
        a_nw = skrf.Network(f=a.f, s=a.s, f_unit='Hz').interpolate(freq_new)
        b_nw = skrf.Network(f=b.f, s=b.s, f_unit='Hz').interpolate(freq_new)
        return a_nw,b_nw
    

    @staticmethod
    def _op(a: "SParam", b: "SParam", op: "callable") -> "SParam":
        if isinstance(a, (int,float,complex,np.ndarray)):
            return SParam(b.name, b.f, op(a,np.array(np.ndarray.flatten(b.s))), z0=b.z0)
        if isinstance(b, (int,float,complex,np.ndarray)):
            return SParam(a.name, a.f, op(np.array(np.ndarray.flatten(a.s)),b), z0=a.z0)
        a_nw, b_nw = SParam._adapt_f(a, b)
        a_s = np.array(np.ndarray.flatten(a_nw.s))
        b_s = np.array(np.ndarray.flatten(b_nw.s))
        c_s = op(a_s, b_s)
        return SParam(a.name, a_nw.f, c_s, a_nw.z0)

        
    def __truediv__(self, other: "SParam|float") -> "SParam":
        return SParam._op(self, other, lambda a,b: a/b)


    def __rtruediv__(self, other: "SParam|float") -> "SParam":
        return SParam._op(other, self, lambda a,b: a/b)

        
    def __mul__(self, other: "SParam|float") -> "SParam":
        return SParam._op(self, other, lambda a,b: a*b)


    def __rmul__(self, other: "SParam|float") -> "SParam":
        return SParam._op(other, self, lambda a,b: a*b)

        
    def __pow__(self, other: "SParam|float") -> "SParam":
        return SParam._op(self, other, lambda a,b: a**b)


    def __rpow__(self, other: "SParam|float") -> "SParam":
        return SParam._op(other, self, lambda a,b: a**b)

        
    def __add__(self, other: "SParam|float") -> "SParam":
        return SParam._op(self, other, lambda a,b: a+b)


    def __radd__(self, other: "SParam|float") -> "SParam":
        return SParam._op(other, self, lambda a,b: a+b)

        
    def __sub__(self, other: "SParam|float") -> "SParam":
        return SParam._op(self, other, lambda a,b: a-b)


    def __rsub__(self, other: "SParam|float") -> "SParam":
        return SParam._op(self, other, lambda a,b: b-a)


    def __invert__(self) -> "SParam":
        return SParam(self.name, self.f, 1/self.s, self.z0)

    
    def abs(self) -> "SParam":
        return SParam(self.name, self.f, np.abs(self.s), self.z0)

    
    def db(self) -> "SParam":
        return SParam(self.name, self.f, 20*np.log10(np.maximum(1e-15,np.abs(self.s))), self.z0)

    
    def db10(self) -> "SParam":
        return SParam(self.name, self.f, 10*np.log10(np.maximum(1e-30,np.abs(self.s))), self.z0)

    
    def db20(self) -> "SParam":
        return SParam(self.name, self.f, 20*np.log10(np.maximum(1e-15,np.abs(self.s))), self.z0)

    
    def ml(self) -> "SParam":
        return SParam(self.name + ' ML', self.f, 1-(np.abs(self.s)**2), self.z0)

    
    def vswr(self) -> "SParam":
        return SParam(self.name + ' VSWR', self.f, (1+np.abs(self.s))/(1-np.abs(self.s)), self.z0)

    
    def phase(self, processing: "str|None" = None) -> "SParam":
        s = self.s
        s = np.angle(s)
        if processing == 'remove_linear':
            s = scipy.signal.detrend(np.unwrap(s), type='linear')
        elif processing == 'unwrap':
            s = np.unwrap(s)
        elif s is not None:
            raise ValueError(f'Invalid processing option "{processing}"')
        return SParam(self.name, self.f, s, self.z0)

    
    def plot(self, label: "str" = None, style: "str" = None):
        if label is None:
            label = self.name
        else:
            label = label.replace('%n', self.name)
        SParam.plot_fn(self.f, self.s, self.z0, label, style)

    
    def crop_f(self, f_start: "float|None" = None, f_end: "float|None" = None) -> "SParam":
        f_start = -1e99 if f_start is None else f_start
        f_end   = +1e99 if f_end   is None else f_end
        new = [(f,s) for (f,s) in zip(self.f, self.s) if f_start<=f<=f_end]
        if len(new)<1:
            raise Exception('SParam.crop_f(): frequency out of range')
        new_f, new_s = zip(*new)
        return SParam(self.name, new_f, new_s, self.z0)
        
    
    def rl_avg(self, f_integrate_start: "float|any" = any, f_integrate_end: "float|any" = any, f_target_start: "float|any" = any, f_target_end: "float|any" = any) -> "SParam":
        
        if f_integrate_start is any:
            f_integrate_start = -1e99
        if f_integrate_end is any:
            f_integrate_end = +1e99
        
        if f_target_start is any or f_target_end is any:
            
            bodefano = BodeFano(self.f, self.s, f_integrate_start, f_integrate_end, f_integrate_start, f_integrate_end)

            if f_target_start is any:
                f_target_start = bodefano.f_integration_actual_start_hz
            if f_target_end is any:
                f_target_end = bodefano.f_integration_actual_stop_hz
        
        bodefano = BodeFano(self.f, self.s, f_integrate_start, f_integrate_end, f_target_start, f_target_end)
        s11_linear = pow(10, bodefano.db_achievable/20)

        f = np.array([f_target_start, f_target_end])
        s = np.array([s11_linear, s11_linear])
        return SParam(self.name, f, s, self.z0)
    
        

    def map(self, fn: "Callable[np.ndarray,np.ndarray]"):
        s = np.array(fn(self.s))
        if s.shape != self.s.shape:
            raise RuntimeError(f'SParam.map(): user-provided function returned a different shape (expected {self.s.shape}, got {s.shape})')
        return SParam(self.name, self.f, s, self.z0)    
    
    def rename(self, name: str=None, prefix: str=None, suffix: str=None, pattern: str=None, subs: str=None):
        new_name = self.name
        if name is not None:
            new_name = name
        if prefix is not None:
            new_name = prefix + new_name
        if suffix is not None:
            new_name = new_name + suffix
        if pattern is not None or subs is not None:
            if pattern is None or subs is None:
                raise ValueError('SParam.rename(): pattern and subs must be specified together')
            new_name = re.sub(pattern, subs, new_name)
        return SParam(new_name, self.f, self.s, self.z0)
    

    def save(self, filename: str):
        
        ext = os.path.splitext(filename)[1].lower()

        s = np.ndarray([len(self.f),1,1], dtype=complex)
        s[:,0,0] = self.s
        nw = skrf.Network(s=s, f=self.f, f_unit='Hz', z0=self.z0, comment=self.name)
        
        if ext=='.cti' or ext=='.citi':
            CitiWriter().write(nw, filename)
        
        elif m := re.match(r'\.s([0-9])+p', ext):
            n = int(m.group(1))
            if n != nw.nports:
                logging.warning(f'Saving {nw.nports}-port into .s{n}p-file.')
            nw.write_touchstone(filename)
        
        elif ext=='.xls' or ext=='.xlsx':
            nw.write_spreadsheet(filename, form='db', file_type='excel')
        
        elif ext=='.csv':
            nw.write_spreadsheet(filename, form='db', file_type='csv')
        
        else:
            raise ValueError(f'Unknown file extension: "{ext}"')

        logging.info(f'Saved parameter <{self.name}> to <{filename}>')
    

    def __repr__(self):
        return f'<SParam("{self.name}", f={self.f}, s={self.s})>'



class SParams:

    def __init__(self, sps: "list[SParam]"):
        self.sps = sps


    def _broadcast(self, sp: "SParams") -> "SParams":
        if isinstance(sp, (int,float,complex,np.ndarray)):
            return [sp] * len(self.sps)
        if not isinstance(sp, SParams):
            raise ValueError('Expected operand of type S-parameters, or numeric')
        if len(sp.sps) == 1:
            return [sp.sps[0]] * len(self.sps)
        elif len(sp.sps) == len(self.sps):
            return self.sps
        raise ValueError(f'Argument has dimension {len(sp.sps)}, but must nave 1 or {len(self.sps)}')
    

    def _unary_op(self, fn, return_sps, **kwargs):
        result = []
        for sp in self.sps:
            try:
                result.append(fn(sp, **kwargs))
            except Exception as ex:
                logging.warning(f'Unary operation <{fn}> on sparam <{sp.name}> failed ({ex}), ignoring')
        if return_sps:
            return SParams(sps=result)
        else:
            return result


    def _binary_op(self, fn, others, return_sps, **kwargs):
        result = []
        for sp,other in zip(self.sps, self._broadcast(others)):
            try:
                result.append(fn(sp, other, **kwargs))
            except Exception as ex:
                logging.warning(f'Binary operation <{fn}> on sparam <{sp.name}> failed ({ex}), ignoring')
        if return_sps:
            return SParams(sps=result)
        else:
            return result

        
    def __truediv__(self, others: "SParams|float") -> "SParams":
        return self._binary_op(SParam.__truediv__, others, True)


    def __rtruediv__(self, others: "SParams|float") -> "SParams":
        return self._binary_op(SParam.__rtruediv__, others, True)

        
    def __mul__(self, others: "SParams|float") -> "SParams":
        return self._binary_op(SParam.__mul__, others, True)


    def __rmul__(self, others: "SParams|float") -> "SParams":
        return self._binary_op(SParam.__rmul__, others, True)

        
    def __pow__(self, others: "SParams|float") -> "SParams":
        return self._binary_op(SParam.__pow__, others, True)


    def __rpow__(self, others: "SParams|float") -> "SParams":
        return self._binary_op(SParam.__rpow__, others, True)
        

    def __add__(self, others: "SParams|float") -> "SParams":
        return self._binary_op(SParam.__add__, others, True)


    def __radd__(self, others: "SParams|float") -> "SParams":
        return self._binary_op(SParam.__radd__, others, True)
        

    def __sub__(self, others: "SParams|float") -> "SParams":
        return self._binary_op(SParam.__sub__, others, True)


    def __rsub__(self, others: "SParams|float") -> "SParams":
        return self._binary_op(SParam.__rsub__, others, True)


    def __invert__(self) -> "SParams":
        return self._unary_op(SParam.__invert__, True)
    

    def abs(self) -> "SParams":
        return self._unary_op(SParam.abs, True)
    

    def db(self) -> "SParams":
        return self._unary_op(SParam.db, True)
    

    def ml(self) -> "SParams":
        return self._unary_op(SParam.ml, True)
    

    def vswr(self) -> "SParams":
        return self._unary_op(SParam.vswr, True)

    
    def phase(self, processing: "str|None" = None) -> "SParams":
        return self._unary_op(SParam.phase, True, processing=processing)
    

    def plot(self, label: "str|None" = None, style: "str|None" = None):
        self._unary_op(SParam.plot, False, label=label, style=style)
    

    def crop_f(self, f_start: "float|None" = None, f_end: "float|None" = None) -> "SParams":
        return self._unary_op(SParam.crop_f, True, f_start=f_start, f_end=f_end)


    def _interpolate(self, f: np.ndarray):
        result = []
        for sp in self.sps:
            try:
                mag, pha = np.abs(sp.s), np.unwrap(np.angle(sp.s))
                mag_int, pha_int = np.interp(f, sp.f, mag), np.interp(f, sp.f, pha)
                s_int = mag_int * np.exp(1j*pha_int)
                result.append(SParam(sp.name, f, s_int, sp.z0))
            except Exception as ex:
                logging.warning(f'Interpolating <{sp.name}> failed ({ex}), ignoring')
        return SParams(sps=result)


    def interpolate_lin(self, f_start: float, f_end: float, n: int):
        assert f_start <= f_end
        assert n >= 1
        return self._interpolate(np.linspace(f_start, f_end, n))


    def interpolate_log(self, f_start: float, f_end: float, n: int):
        assert f_start > 0
        assert f_start <= f_end
        assert n >= 1
        return self._interpolate(np.geomspace(f_start, f_end, n))


    def interpolate(self, n: int = None):
        all_f = [sp.f for sp in self.sps]
        f_start = np.min(all_f)
        f_stop = np.max(all_f)
        if n is None:
            n = max(3, int(round(np.mean([len(f) for f in all_f]))))
        return self.interpolate_lin(f_start, f_stop, n)


    def _interpolated_fn(self, name, fn, min_size=1):
        sps = self.interpolate().sps
        if len(sps) < min_size:
            return []
        f = sps[0].f
        s = fn([sp.s for sp in sps])
        return SParams(sps=[SParam(name, f, s, math.nan)])


    def mean(self):
        return self._interpolated_fn('Mean', lambda s: np.mean(s,axis=0))


    def median(self):
        return self._interpolated_fn('Median', lambda s: np.median(s,axis=0))


    def sdev(self, ddof=1):
        return self._interpolated_fn('StdDev', lambda s: np.std(s,axis=0,ddof=ddof), min_size=2)
    

    def rl_avg(self, f_integrate_start: "float|any" = any, f_integrate_end: "float|any" = any, f_target_start: "float|any" = any, f_target_end: "float|any" = any) -> "SParams":
        return self._unary_op(SParam.rl_avg, True, f_integrate_start=f_integrate_start, f_integrate_end=f_integrate_end, f_target_start=f_target_start, f_target_end=f_target_end)
    

    def map(self, fn: "Callable[np.ndarray,np.ndarray]"):
        return SParams(sps=[s.map(fn) for s in self.sps])

    
    def rename(self, name: str=None, prefix: str=None, suffix: str=None, pattern: str=None, subs: str=None):
        return self._unary_op(SParam.rename, True, name=name, prefix=prefix, suffix=suffix, pattern=pattern, subs=subs)
    

    def save(self, filename: str):
        WILDCARD = '$$'
        
        if len(self.sps) > 1:
            if WILDCARD not in filename:
                raise RuntimeError(f'Please add a wildcard ("{WILDCARD}") to the filename if you want to save multiple parameters.')
        
        for sp in self.sps:
            [directory, name] = os.path.split(filename)
            [name, ext] = os.path.splitext(name)
            name = sanitize_filename(name.replace(WILDCARD, sp.name))
            path = os.path.join(directory, name+ext)
            sp.save(path)
    

    def __repr__(self):
        if len(self.sps) == 1:
            return f'<SParams({self.sps[0]})>'
        return f'<SParams({len(self.sps)}x SParam, 1st is {self.sps[0]})>'
    
    
    def _count(self) -> int:
        return len(self.sps)
