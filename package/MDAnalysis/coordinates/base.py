# -*- Mode: python; tab-width: 4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 fileencoding=utf-8
#
# MDAnalysis --- http://www.MDAnalysis.org
# Copyright (c) 2006-2015 Naveen Michaud-Agrawal, Elizabeth J. Denning, Oliver Beckstein
# and contributors (see AUTHORS for the full list)
#
# Released under the GNU Public Licence, v2 or any higher version
#
# Please cite your use of MDAnalysis in published work:
#
# N. Michaud-Agrawal, E. J. Denning, T. B. Woolf, and O. Beckstein.
# MDAnalysis: A Toolkit for the Analysis of Molecular Dynamics Simulations.
# J. Comput. Chem. 32 (2011), 2319--2327, doi:10.1002/jcc.21787
#


"""
Base classes --- :mod:`MDAnalysis.coordinates.base`
====================================================

Derive other Timestep, Reader and Writer classes from the classes in this
module. The derived classes must follow the Trajectory API in
:mod:`MDAnalysis.coordinates.__init__`.

.. class:: Timestep

   .. automethod:: __init__
   .. automethod:: from_coordinates
   .. automethod:: from_timestep
   .. automethod:: _init_unitcell
   .. autoattribute:: numatoms
   .. attribute::`frame`

      frame number (0-based)

      .. versionchanged:: 0.11.0
         Frames now 0-based; was 1-based

   .. autoattribute:: time
   .. autoattribute:: dt
   .. autoattribute:: positions
   .. autoattribute:: velocities
   .. autoattribute:: forces
   .. autoattribute:: has_positions
   .. autoattribute:: has_velocities
   .. autoattribute:: has_forces
   .. attribute:: _pos

      :class:`numpy.ndarray` of dtype :class:`~numpy.float32` of shape
      (*numatoms*, 3) and internal FORTRAN order, holding the raw
      cartesian coordinates (in MDAnalysis units, i.e. Å).

      .. Note::

         Normally one does not directly access :attr:`_pos` but uses
         the :meth:`~MDAnalysis.core.AtomGroup.AtomGroup.coordinates`
         method of an :class:`~MDAnalysis.core.AtomGroup.AtomGroup` but
         sometimes it can be faster to directly use the raw
         coordinates. Any changes to this array are immediately
         reflected in atom positions. If the frame is written to a new
         trajectory then the coordinates are changed. If a new
         trajectory frame is loaded, then *all* contents of
         :attr:`_pos` are overwritten.

   .. attribute:: _velocities

      :class:`numpy.ndarray` of dtype :class:`~numpy.float32`. of shape
      (*numatoms*, 3), holding the raw velocities (in MDAnalysis
      units, i.e. typically Å/ps).

      .. Note::

         Normally velocities are accessed through the
         :attr:`velocities` or the
         :meth:`~MDAnalysis.core.AtomGroup.AtomGroup.velocities`
         method of an :class:`~MDAnalysis.core.AtomGroup.AtomGroup`

         :attr:`~Timestep._velocities` only exists if the :attr:`has_velocities`
         flag is True

      .. versionadded:: 0.7.5

   .. attribute:: _forces

      :class:`numpy.ndarray` of dtype :class:`~numpy.float32`. of shape
      (*numatoms*, 3), holding the forces

      :attr:`~Timestep._forces` only exists if :attr:`has_forces`
      is True

      .. versionadded:: 0.11.0
         Added as optional to :class:`Timestep`

   .. autoattribute:: dimensions
   .. autoattribute:: triclinic_dimensions
   .. autoattribute:: volume
   .. automethod:: __getitem__
   .. automethod:: __eq__
   .. automethod:: __iter__
   .. automethod:: copy
   .. automethod:: copy_slice

.. autoclass:: IObase
   :members:

.. autoclass:: Reader
   :members:

.. autoclass:: ChainReader
   :members:

.. autoclass:: Writer
   :members:

"""

import itertools
import os.path
import warnings
import bisect
import numpy as np
import copy

from ..core import flags
from .. import units
from ..lib.util import asiterable
from . import core
from .. import NoDataError


class Timestep(object):
    """Timestep data for one frame

    :Methods:

      ``ts = Timestep(numatoms)``

         create a timestep object with space for numatoms

    .. versionchanged:: 0.11.0
       Added :meth:`from_timestep` and :meth:`from_coordinates` constructor
       methods.
       :class:`Timestep` init now only accepts integer creation
       :attr:`numatoms` now a read only property
       :attr:`frame` now 0-based instead of 1-based
       Attributes status and step removed
    """
    order = 'F'

    def __init__(self, numatoms, **kwargs):
        """Create a Timestep, representing a frame of a trajectory

        :Arguments:
          *numatoms*
            The total number of atoms this Timestep describes

        :Keywords:
          *positions*
            Whether this Timestep has position information [``True``]
          *velocities*
            Whether this Timestep has velocity information [``False``]
          *forces*
            Whether this Timestep has force information [``False``]
          *dt*
            The time difference between frames (ps).  If :attr:`time`
            is set, then `dt` will be ignored.
          *time_offset*
            The starting time from which to calculate time (ps)

        .. versionchanged:: 0.11.0
           Added keywords for positions, velocities and forces
           Can add and remove position/velocity/force information by using
           the has_* attribute
        """
        # readers call Reader._read_next_timestep() on init, incrementing
        # self.frame to 0
        self.frame = -1
        self._numatoms = numatoms

        self.data = {}

        for att in ('dt', 'time_offset'):
            try:
                self.data[att] = kwargs[att]
            except KeyError:
                pass

        # Stupid hack to make it allocate first time round
        # ie we have to go from not having, to having positions
        # to make the Timestep allocate
        self._has_positions = False
        self._has_velocities = False
        self._has_forces = False

        # These will allocate the arrays if the has flag
        # gets set to True
        self.has_positions = kwargs.get('positions', True)
        self.has_velocities = kwargs.get('velocities', False)
        self.has_forces = kwargs.get('forces', False)

        self._unitcell = self._init_unitcell()

    @classmethod
    def from_timestep(cls, other, **kwargs):
        """Create a copy of another Timestep, in the format of this Timestep

        .. versionadded:: 0.11.0
        """
        ts = cls(other.numatoms, velocities=other.has_velocities,
                 forces=other.has_forces, **kwargs)
        ts.frame = other.frame
        ts.dimensions = other.dimensions
        try:
            ts.positions = other.positions.copy(order=cls.order)
        except NoDataError:
            pass
        try:
            ts.velocities = other.velocities.copy(order=cls.order)
        except NoDataError:
            pass
        try:
            ts.forces = other.forces.copy(order=cls.order)
        except NoDataError:
            pass

        for att in ('_frame', '_time'):
            try:
                setattr(ts, att, getattr(other, att))
            except AttributeError:
                pass

        ts.time = other.time
        ts.data = copy.deepcopy(other.data)

        return ts

    @classmethod
    def from_coordinates(cls, positions, velocities=None, forces=None, **kwargs):
        """Create an instance of this Timestep, from coordinate data

        .. versionadded:: 0.11.0
        """
        has_velocities = velocities is not None
        has_forces = forces is not None

        ts = cls(len(positions), velocities=has_velocities, forces=has_forces, **kwargs)
        ts.positions = positions
        if has_velocities:
            ts.velocities = velocities
        if has_forces:
            ts.forces = forces

        return ts

    def _init_unitcell(self):
        """Create custom datastructure for :attr:`_unitcell`."""
        # override for other Timesteps
        return np.zeros((6), np.float32)

    def __eq__(self, other):
        """Compare with another Timestep

        .. versionadded:: 0.11.0
        """
        if not isinstance(other, Timestep):
            return False

        if not self.frame == other.frame:
            return False

        if not self.numatoms == other.numatoms:
            return False

        # Check contents of np arrays last (probably slow)
        if not (self.positions == other.positions).all():
            return False
        if not self.has_velocities == other.has_velocities:
            return False
        if self.has_velocities:
            if not (self.velocities == other.velocities).all():
                return False
        if not self.has_forces == other.has_forces:
            return False
        if self.has_forces:
            if not (self.forces == other.forces).all():
                return False

        return True

    def __getitem__(self, atoms):
        """Get a selection of coordinates

        ``ts[i]``

           return coordinates for the i'th atom (0-based)

        ``ts[start:stop:skip]``

           return an array of coordinates, where start, stop and skip
           correspond to atom indices,
           :attr:`MDAnalysis.core.AtomGroup.Atom.number` (0-based)
        """
        if isinstance(atoms, int):
            return self._pos[atoms]
        elif isinstance(atoms, (slice, np.ndarray)):
            return self._pos[atoms]
        else:
            raise TypeError

    def __len__(self):
        return self.numatoms

    def __iter__(self):
        """Iterate over coordinates

        ``for x in ts``

            iterate of the coordinates, atom by atom
        """
        for i in xrange(self.numatoms):
            yield self[i]

    def __repr__(self):
        desc = "< Timestep {0}".format(self.frame)
        try:
            tail = " with unit cell dimensions {0} >".format(self.dimensions)
        except NotImplementedError:
            tail = " >"
        return desc + tail

    def copy(self):
        """Make an independent ("deep") copy of the whole :class:`Timestep`."""
        return self.__deepcopy__()

    def __deepcopy__(self):
        return self.from_timestep(self)

    def copy_slice(self, sel):
        """Make a new Timestep containing a subset of the original Timestep.

        ``ts.copy_slice(slice(start, stop, skip))``
        ``ts.copy_slice([list of indices])``

        :Returns: A Timestep object of the same type containing all header
                  information and all atom information relevant to the selection.

        .. Note:: The selection must be a 0 based slice or array of the atom indices
                  in this Timestep

        .. versionadded:: 0.8
        .. versionchanged:: 0.11.0
           Reworked to follow new Timestep API.  Now will strictly only
           copy official attributes of the Timestep.
        """
        # Detect the size of the Timestep by doing a dummy slice
        try:
            new_numatoms = len(self._pos[sel])
        except:
            raise TypeError("Selection type must be compatible with slicing"
                            " the coordinates")
        # Make a mostly empty TS of same type of reduced size
        new_TS = self.__class__(new_numatoms, velocities=self.has_velocities,
                                forces=self.has_forces)

        if self.has_positions:
            new_TS.positions = self.positions[sel]
        if self.has_velocities:
            new_TS.velocities = self.velocities[sel]
        if self.has_forces:
            new_TS.forces = self.forces[sel]
        new_TS._unitcell = self._unitcell.copy()

        new_TS.time = self.time
        new_TS.frame = self.frame

        for att in ('_frame', '_time'):
            try:
                setattr(new_TS, att, getattr(self, att))
            except AttributeError:
                pass

        new_TS.data = copy.deepcopy(self.data)

        return new_TS

    @property
    def numatoms(self):
        """A read only view of the number of atoms this Timestep has

        .. versionchanged:: 0.11.0
           Changed to read only property
        """
        # In future could do some magic here to make setting numatoms
        # resize the coordinate arrays, but
        # - not sure if that is ever useful
        # - not sure how to manage existing data upon extension
        return self._numatoms

    @property
    def has_positions(self):
        """A boolean of whether this Timestep has position data

        This can be changed to ``True`` or ``False`` to allocate space for
        or remove the data.

        .. versionadded:: 0.11.0
        """
        return self._has_positions

    @has_positions.setter
    def has_positions(self, val):
        if val and not self._has_positions:
            # Setting this will always reallocate position data
            # ie
            # True -> False -> True will wipe data from first True state
            self._pos = np.zeros((self.numatoms, 3), dtype=np.float32,
                                 order=self.order)
            self._has_positions = True
        elif not val:
            # Unsetting val won't delete the numpy array
            self._has_positions = False

    @property
    def positions(self):
        """A record of the positions of all atoms in this Timestep

        Setting this attribute will add positions to the Timestep if they
        weren't originally present.

        :Returns:
           A numpy.ndarray of shape (numatoms, 3) of position data for each
           atom

        :Raises:
           :class:`MDAnalysis.exceptions.NoDataError`
              If the Timestep has no position data

        .. versionchanged:: 0.11.0
           Now can raise NoDataError when no position data present
        """
        if self.has_positions:
            return self._pos
        else:
            raise NoDataError("This Timestep has no positions")

    @positions.setter
    def positions(self, new):
        self.has_positions = True
        self._pos[:] = new

    @property
    def _x(self):
        """A view onto the x dimension of position data

        .. versionchanged:: 0.11.0
           Now read only
        """
        return self.positions[:, 0]

    @property
    def _y(self):
        """A view onto the y dimension of position data

        .. versionchanged:: 0.11.0
           Now read only
        """
        return self.positions[:, 1]

    @property
    def _z(self):
        """A view onto the z dimension of position data

        .. versionchanged:: 0.11.0
           Now read only
        """
        return self.positions[:, 2]

    @property
    def has_velocities(self):
        """A boolean of whether this Timestep has velocity data

        This can be changed to ``True`` or ``False`` to allocate space for
        or remove the data.

        .. versionadded:: 0.11.0
        """
        return self._has_velocities

    @has_velocities.setter
    def has_velocities(self, val):
        if val and not self._has_velocities:
            self._velocities = np.zeros((self.numatoms, 3), dtype=np.float32,
                                        order=self.order)
            self._has_velocities = True
        elif not val:
            self._has_velocities = False

    @property
    def velocities(self):
        """A record of the velocities of all atoms in this Timestep

        Setting this attribute will add velocities to the Timestep if they
        weren't originally present.

        :Returns:
           A numpy.ndarray of shape (numatoms, 3) of velocity data for each
           atom

        :Raises:
           :class:`MDAnalysis.exceptions.NoDataError`
              When the Timestep does not contain velocity information

        .. versionadded:: 0.11.0
        """
        if self.has_velocities:
            return self._velocities
        else:
            raise NoDataError("This Timestep has no velocities")

    @velocities.setter
    def velocities(self, new):
        self.has_velocities = True
        self._velocities[:] = new

    @property
    def has_forces(self):
        """A boolean of whether this Timestep has force data

        This can be changed to ``True`` or ``False`` to allocate space for
        or remove the data.

        .. versionadded:: 0.11.0
        """
        return self._has_forces

    @has_forces.setter
    def has_forces(self, val):
        if val and not self._has_forces:
            self._forces = np.zeros((self.numatoms, 3), dtype=np.float32,
                                    order=self.order)
            self._has_forces = True
        elif not val:
            self._has_forces = False

    @property
    def forces(self):
        """A record of the forces of all atoms in this Timestep

        Setting this attribute will add forces to the Timestep if they
        weren't originally present.

        :Returns:
           A numpy.ndarray of shape (numatoms, 3) of force data for each
           atom

        :Raises:
           :class:`MDAnalysis.NoDataError`
              When the Timestep does not contain force information

        .. versionadded:: 0.11.0
        """
        if self.has_forces:
            return self._forces
        else:
            raise NoDataError("This Timestep has no forces")

    @forces.setter
    def forces(self, new):
        self.has_forces = True
        self._forces[:] = new

    @property
    def dimensions(self):
        """unitcell dimensions (*A*, *B*, *C*, *alpha*, *beta*, *gamma*)

        lengths *a*, *b*, *c* are in the MDAnalysis length unit (Å), and
        angles are in degrees.

        Setting dimensions will populate the underlying native format
        description of box dimensions
        """
        # The actual Timestep._unitcell depends on the underlying
        # trajectory format. It can be e.g. six floats representing
        # the box edges and angles or the 6 unique components of the
        # box matrix or the full box matrix.
        return self._unitcell

    @dimensions.setter
    def dimensions(self, box):
        self._unitcell[:] = box

    @property
    def volume(self):
        """volume of the unitcell"""
        return core.box_volume(self.dimensions)

    @property
    def triclinic_dimensions(self):
        """The unitcell dimensions represented as triclinic vectors

        :Returns:
           A (3, 3) numpy.ndarray of unit cell vectors

        For example::

          >>> ts.dimensions
          array([ 13.,  14.,  15.,  90.,  90.,  90.], dtype=float32)
          >>> ts.triclinic_dimensions
          array([[ 13.,   0.,   0.],
                 [  0.,  14.,   0.],
                 [  0.,   0.,  15.]], dtype=float32)

        Setting the attribute also works::

          >>> ts.triclinic_dimensions = [[15, 0, 0], [5, 15, 0], [5, 5, 15]]
          >>> ts.dimensions
          array([ 15.        ,  15.81138802,  16.58312416,  67.58049774,
                  72.45159912,  71.56504822], dtype=float32)

        .. SeeAlso::
           :func:`MDAnalysis.lib.mdamath.triclinic_vectors`

        .. versionadded:: 0.11.0
        """
        return core.triclinic_vectors(self.dimensions)

    @triclinic_dimensions.setter
    def triclinic_dimensions(self, new):
        """Set the unitcell for this Timestep as defined by triclinic vectors

        .. versionadded:: 0.11.0
        """
        self.dimensions = core.triclinic_box(*new)

    @property
    def dt(self):
        """The time difference in ps between timesteps

        .. Note::
           This defaults to 1.0 ps in the absence of time data

        .. versionadded:: 0.11.0
        """
        try:
            return self.data['dt']
        except KeyError:
            warnings.warn("Reader has no dt information, set to 1.0 ps")
            return 1.0

    @dt.setter
    def dt(self, new):
        self.data['dt'] = new

    @dt.deleter
    def dt(self):
        del self.data['dt']

    @property
    def time(self):
        """The time in ps of this timestep

        This is calculated as::

          time = ts.data['time_offset'] + ts.time

        Or, if the trajectory doesn't provide time information::

          time = ts.data['time_offset'] + ts.frame * ts.dt

        .. versionadded:: 0.11.0
        """
        offset = self.data.get('time_offset', 0)
        try:
            return self.data['time'] + offset
        except KeyError:
            return self.dt * self.frame + offset

    @time.setter
    def time(self, new):
        self.data['time'] = new

    @time.deleter
    def time(self):
        del self.data['time']


class IObase(object):
    """Base class bundling common functionality for trajectory I/O.

    .. versionchanged:: 0.8
       Added context manager protocol.
    """
    #: override to define trajectory format of the reader/writer (DCD, XTC, ...)
    format = None

    #: dict with units of of *time* and *length* (and *velocity*, *force*,
    #: ... for formats that support it)
    units = {'time': None, 'length': None, 'velocity': None}

    def convert_pos_from_native(self, x, inplace=True):
        """In-place conversion of coordinate array x from native units to base units.

        By default, the input *x* is modified in place and also returned.

        .. versionchanged:: 0.7.5
           Keyword *inplace* can be set to ``False`` so that a
           modified copy is returned *unless* no conversion takes
           place, in which case the reference to the unmodified *x* is
           returned.

        """
        f = units.get_conversion_factor('length', self.units['length'], flags['length_unit'])
        if f == 1.:
            return x
        if not inplace:
            return f * x
        x *= f
        return x

    def convert_velocities_from_native(self, v, inplace=True):
        """In-place conversion of velocities array *v* from native units to base units.

        By default, the input *v* is modified in place and also returned.

        .. versionadded:: 0.7.5
        """
        f = units.get_conversion_factor('speed', self.units['velocity'], flags['speed_unit'])
        if f == 1.:
            return v
        if not inplace:
            return f * v
        v *= f
        return v

    def convert_forces_from_native(self, force, inplace=True):
        """In-place conversion of forces array *force* from native units to base units.

        By default, the input *force* is modified in place and also returned.

        .. versionadded:: 0.7.7
        """
        f = units.get_conversion_factor('force', self.units['force'], flags['force_unit'])
        if f == 1.:
            return force
        if not inplace:
            return f * force
        force *= f
        return force

    def convert_time_from_native(self, t, inplace=True):
        """Convert time *t* from native units to base units.

        By default, the input *t* is modified in place and also
        returned (although note that scalar values *t* are passed by
        value in Python and hence an in-place modification has no
        effect on the caller.)

        .. versionchanged:: 0.7.5
           Keyword *inplace* can be set to ``False`` so that a
           modified copy is returned *unless* no conversion takes
           place, in which case the reference to the unmodified *x* is
           returned.

        """
        f = units.get_conversion_factor('time', self.units['time'], flags['time_unit'])
        if f == 1.:
            return t
        if not inplace:
            return f * t
        t *= f
        return t

    def convert_pos_to_native(self, x, inplace=True):
        """Conversion of coordinate array x from base units to native units.

        By default, the input *x* is modified in place and also returned.

        .. versionchanged:: 0.7.5
           Keyword *inplace* can be set to ``False`` so that a
           modified copy is returned *unless* no conversion takes
           place, in which case the reference to the unmodified *x* is
           returned.

        """
        f = units.get_conversion_factor('length', flags['length_unit'], self.units['length'])
        if f == 1.:
            return x
        if not inplace:
            return f * x
        x *= f
        return x

    def convert_velocities_to_native(self, v, inplace=True):
        """In-place conversion of coordinate array *v* from base units to native units.

        By default, the input *v* is modified in place and also returned.

        .. versionadded:: 0.7.5
        """
        f = units.get_conversion_factor('speed', flags['speed_unit'], self.units['velocity'])
        if f == 1.:
            return v
        if not inplace:
            return f * v
        v *= f
        return v

    def convert_forces_to_native(self, force, inplace=True):
        """In-place conversion of force array *force* from base units to native units.

        By default, the input *force* is modified in place and also returned.

        .. versionadded:: 0.7.7
        """
        f = units.get_conversion_factor('force', flags['force_unit'], self.units['force'])
        if f == 1.:
            return force
        if not inplace:
            return f * force
        force *= f
        return force

    def convert_time_to_native(self, t, inplace=True):
        """Convert time *t* from base units to native units.

        By default, the input *t* is modified in place and also
        returned. (Also note that scalar values *t* are passed by
        value in Python and hence an in-place modification has no
        effect on the caller.)

        .. versionchanged:: 0.7.5
           Keyword *inplace* can be set to ``False`` so that a
           modified copy is returned *unless* no conversion takes
           place, in which case the reference to the unmodified *x* is
           returned.

        """
        f = units.get_conversion_factor('time', flags['time_unit'], self.units['time'])
        if f == 1.:
            return t
        if not inplace:
            return f * t
        t *= f
        return t

    def close(self):
        """Close the trajectory file."""
        pass

    # experimental:  context manager protocol
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # see http://docs.python.org/2/library/stdtypes.html#typecontextmanager
        self.close()
        return False  # do not suppress exceptions


class ProtoReader(IObase):
    """Base class for Readers, without a :meth:`__del__` method.

    Extends :class:`IObase` with most attributes and methods of a generic
    Reader, with the exception of a :meth:`__del__` method. It should be used
    as base for Readers that do not need :meth:`__del__`, especially since
    having even an empty :meth:`__del__` might lead to memory leaks.

    See the :ref:`Trajectory API` definition in
    :mod:`MDAnalysis.coordinates.__init__` for the required attributes and
    methods.

    .. SeeAlso:: :class:`Reader`

    .. versionchanged:: 0.11.0
       Frames now 0-based instead of 1-based
    """

    #: The appropriate Timestep class, e.g.
    #: :class:`MDAnalysis.coordinates.xdrfile.XTC.Timestep` for XTC.
    _Timestep = Timestep

    def __len__(self):
        return self.numframes

    def next(self):
        """Forward one step to next frame."""
        return self._read_next_timestep()

    def rewind(self):
        """Position at beginning of trajectory"""
        self._reopen()
        self.next()

    @property
    def dt(self):
        """Time between two trajectory frames in picoseconds."""
        return self.ts.dt

    @property
    def totaltime(self):
        """Total length of the trajectory numframes * dt."""
        return self.numframes * self.dt

    @property
    def frame(self):
        """Frame number of the current time step.

        This is a simple short cut to :attr:`Timestep.frame`.
        """
        return self.ts.frame

    @property
    def time(self):
        """Time of the current frame in MDAnalysis time units (typically ps).

        This is either read straight from the Timestep, or calculated as
        time = :attr:`Timestep.frame` * :attr:`Timestep.dt`
        """
        return self.ts.time

    def Writer(self, filename, **kwargs):
        """Returns a trajectory writer with the same properties as this trajectory."""
        raise NotImplementedError("Sorry, there is no Writer for this format in MDAnalysis. "
                "Please file an enhancement request at https://github.com/MDAnalysis/mdanalysis/issues")

    def OtherWriter(self, filename, **kwargs):
        """Returns a writer appropriate for *filename*.

        Sets the default keywords *start*, *step* and *dt* (if
        available). *numatoms* is always set from :attr:`Reader.numatoms`.

        .. SeeAlso:: :meth:`Reader.Writer` and :func:`MDAnalysis.Writer`
        """
        kwargs['numatoms'] = self.numatoms  # essential
        kwargs.setdefault('start', self.frame)
        try:
            kwargs.setdefault('dt', self.dt)
        except KeyError:
            pass
        return core.writer(filename, **kwargs)

    def _read_next_timestep(self, ts=None):
        # Example from DCDReader:
        #     if ts is None: ts = self.ts
        #     ts.frame = self._read_next_frame(ts._x, ts._y, ts._z, ts._unitcell, self.skip)
        #     return ts
        raise NotImplementedError("BUG: Override _read_next_timestep() in the trajectory reader!")

    def __iter__(self):
        self._reopen()
        while True:
            try:
                yield self._read_next_timestep()
            except (EOFError, IOError):
                self.rewind()
                raise StopIteration

    def _reopen(self):
        """Should position Reader to just before first frame

        Calling next after this should return the first frame
        """
        pass

    def __getitem__(self, frame):
        """Return the Timestep corresponding to *frame*.

        If *frame* is a integer then the corresponding frame is
        returned. Negative numbers are counted from the end.

        If frame is a :class:`slice` then an iterator is returned that
        allows iteration over that part of the trajectory.

        .. Note:: *frame* is a 0-based frame index.
        """
        if (np.dtype(type(frame)) != np.dtype(int)) and (type(frame) != slice):
            raise TypeError("The frame index (0-based) must be either an integer or a slice")
        if (np.dtype(type(frame)) == np.dtype(int)):
            if (frame < 0):
                # Interpret similar to a sequence
                frame = len(self) + frame
            if (frame < 0) or (frame >= len(self)):
                raise IndexError("Index %d exceeds length of trajectory (%d)." % (frame, len(self)))
            return self._read_frame(frame)  # REPLACE WITH APPROPRIATE IMPLEMENTATION
        elif type(frame) == slice:  # if frame is a slice object
            start, stop, step = self._check_slice_indices(frame.start, frame.stop, frame.step)
            if start == 0 and stop == len(self) and step == 1:
                return self.__iter__()
            else:
                return self._sliced_iter(start, stop, step)

    def _read_frame(self, frame):
        """Move to *frame* and fill timestep with data."""
        raise TypeError("{0} does not support direct frame indexing."
                        "".format(self.__class__.__name__))
        # Example implementation in the DCDReader:
        #self._jump_to_frame(frame)
        #ts = self.ts
        #ts.frame = self._read_next_frame(ts._x, ts._y, ts._z, ts._unitcell, 1) # XXX required!!
        #return ts

    def _sliced_iter(self, start, stop, step):
        """Generator for slicing a trajectory.

        *start* *stop* and *step* are 3 integers describing the slice.
        Error checking is not done past this point.

        A :exc:`NotImplementedError` is raised if random access to
        frames is not implemented.
        """
        # override with an appropriate implementation e.g. using self[i] might
        # be much slower than skipping steps in a next() loop
        def _iter(start=start, stop=stop, step=step):
            try:
                for i in xrange(start, stop, step):
                    yield self._read_frame(i)
            except TypeError:  # if _read_frame not implemented
                raise TypeError("{0} does not support slicing."
                                "".format(self.__class__.__name__))
        return _iter()

    def _check_slice_indices(self, start, stop, step):
        """Unpack the slice object and do checks

        Return the start stop and step indices
        """
        if not (((type(start) == int) or (start is None)) and
                ((type(stop) == int) or (stop is None)) and
                ((type(step) == int) or (step is None))):
            raise TypeError("Slice indices are not integers")
        if step == 0:
            raise ValueError("Step size is zero")

        n = len(self)
        step = step or 1

        if start:
            if start < 0:
                start += n
        else:
            start = 0 if step > 0 else n - 1

        if stop:
            if stop < 0:
                stop += n
            elif stop > n:
                stop = n
        else:
            stop = n if step > 0 else -1

        if step > 0 and stop <= start:
            raise IndexError("Stop frame is lower than start frame")
        if ((start < 0) or (start >= n) or (stop > n)):
            raise IndexError("Frame start/stop outside of the range of the trajectory.")

        return start, stop, step

    def __repr__(self):
        return "< %s %r with %d frames of %d atoms>" % \
               (self.__class__.__name__, self.filename, self.numframes, self.numatoms)

class Reader(ProtoReader):
    """Base class for trajectory readers that extends :class:`ProtoReader` with a :meth:`__del__` method.

    New Readers should subclass :class:`Reader` and properly implement a
    :meth:`close` method, to ensure proper release of resources (mainly file
    handles). Readers that are inherently safe in this regard should subclass
    :class:`ProtoReader` instead.

    See the :ref:`Trajectory API` definition in
    :mod:`MDAnalysis.coordinates.__init__` for the required attributes and
    methods.

    .. SeeAlso:: :class:`ProtoReader`

    .. versionchanged:: 0.11.0
       Most of the base Reader class definitions were offloaded to
       :class:`ProtoReader` so as to allow the subclassing of Readers without a
       :meth:`__del__` method.  Created init method to create common
       functionality, all Reader subclasses must now :func:`super` through this
       class.  Added attribute :attr:`_ts_kwargs`, which is created in init.
       Provides kwargs to be passed to :class:`Timestep`
    """
    def __init__(self, filename, convert_units=None, **kwargs):
        self.filename = filename

        if convert_units is None:
            convert_units = flags['convert_lengths']
        self.convert_units = convert_units

        ts_kwargs = {}
        for att in ('dt', 'time_offset'):
            try:
                val = kwargs[att]
            except KeyError:
                pass
            else:
                ts_kwargs[att] = val

        self._ts_kwargs = ts_kwargs

    def __del__(self):
        self.close()

class ChainReader(ProtoReader):
    """Reader that concatenates multiple trajectories on the fly.

    **Known issues**

    - Trajectory API attributes exist but most of them only reflect
      the first trajectory in the list; :attr:`ChainReader.numframes`,
      :attr:`ChainReader.numatoms`, and :attr:`ChainReader.fixed` are
      properly set, though

    - slicing not implemented

    - :attr:`time` will not necessarily return the true time but just
      number of frames times a provided time between frames (from the
      keyword *delta*)

    .. versionchanged:: 0.11.0
       Frames now 0-based instead of 1-based
    """
    format = 'CHAIN'

    def __init__(self, filenames, **kwargs):
        """Set up the chain reader.

        :Arguments:
           *filenames*
               file name or list of file names; the reader will open
               all file names and provide frames in the order of
               trajectories from the list. Each trajectory must
               contain the same number of atoms in the same order
               (i.e. they all must belong to the same topology). The trajectory
               format is deduced from the extension of *filename*.

               Extension: filenames are either single filename or list of file names in either plain file names
               format or (filename,format) tuple combination

           *skip*
               skip step (also passed on to the individual trajectory
               readers); must be same for all trajectories

           *delta*
               The time between frames in MDAnalysis time units if no
               other information is available. If this is not set then
               any call to :attr:`~ChainReader.time` will raise a
               :exc:`ValueError`.

           *kwargs*
               all other keyword arguments are passed on to each
               trajectory reader unchanged

        .. versionchanged:: 0.8
           The *delta* keyword was added.
        """
        self.filenames = asiterable(filenames)
        self.readers = [core.reader(filename, **kwargs) for filename in self.filenames]
        self.__active_reader_index = 0  # pointer to "active" trajectory index into self.readers

        self.skip = kwargs.get('skip', 1)
        self._default_delta = kwargs.pop('delta', None)
        self.numatoms = self._get_same('numatoms')
        #self.fixed = self._get_same('fixed')

        # Translation between virtual frames and frames in individual
        # trajectories.
        # Assumes that individual trajectories i contain frames that can
        # be addressed with an index 0 <= f < numframes[i]

        # Build a map of frames: ordered list of starting virtual
        # frames; the index i into this list corresponds to the index
        # into self.readers
        #
        # For virtual frame k (1...sum(numframes)) find corresponding
        # trajectory i and local frame f (i.e. readers[i][f] will
        # correspond to ChainReader[k]).

        # build map 'start_frames', which is used by _get_local_frame()
        numframes = self._get('numframes')
        # [0]: frames are 0-indexed internally
        # (see Timestep._check_slice_indices())
        self.__start_frames = np.cumsum([0] + numframes)

        self.numframes = np.sum(numframes)

        #: source for trajectories frame (fakes trajectory)
        self.__chained_trajectories_iter = None

        # make sure that iteration always yields frame 1
        # rewind() also sets self.ts
        self.ts = None
        self.rewind()

    def _get_local_frame(self, k):
        """Find trajectory index and trajectory frame for chained frame k.

        Frame *k* in the chained trajectory can be found in the
        trajectory at index *i* and frame index *f*.

        Frames are internally treated as 0-based indices into the
        trajectory. (This might not be fully consistent across
        MDAnalysis at the moment!)

        :Returns: **local frame** tuple `(i, f)`

        :Raises: :exc:`IndexError` for `k<0` or `i<0`.

        .. Note::

           Does not check if *k* is larger than the maximum number of frames in
           the chained trajectory.
        """
        if k < 0:
            raise IndexError("Virtual (chained) frames must be >= 0")
        # trajectory index i
        i = bisect.bisect_right(self.__start_frames, k) - 1
        if i < 0:
            raise IndexError("Cannot find trajectory for virtual frame %d" % k)
        # local frame index f in trajectory i (frame indices are 0-based)
        f = k - self.__start_frames[i]
        return i, f

    # methods that can change with the current reader
    def convert_time_from_native(self, t):
        return self.active_reader.convert_time_from_native(t)

    def convert_time_to_native(self, t):
        return self.active_reader.convert_time_to_native(t)

    def convert_pos_from_native(self, x):
        return self.active_reader.convert_from_native(x)

    def convert_pos_to_native(self, x):
        return self.active_reader.convert_pos_to_native(x)

    # attributes that can change with the current reader
    @property
    def filename(self):
        return self.active_reader.filename

    @property
    def skip_timestep(self):
        return self.active_reader.skip_timestep

    @property
    def delta(self):
        return self.active_reader.delta

    @property
    def periodic(self):
        return self.active_reader.periodic

    @property
    def units(self):
        return self.active_reader.units

    @property
    def compressed(self):
        try:
            return self.active_reader.compressed
        except AttributeError:
            return None

    @property
    def frame(self):
        """Cumulative frame number of the current time step."""
        return self.ts.frame

    @property
    def time(self):
        """Cumulative time of the current frame in MDAnalysis time units (typically ps)."""
        # currently a hack, should really use a list of trajectory lengths and delta * local_frame
        try:
            return self.frame * self._default_delta
        except TypeError:
            raise ValueError("No timestep information available. Set delta to fake a constant time step.")

    def _apply(self, method, **kwargs):
        """Execute *method* with *kwargs* for all readers."""
        return [reader.__getattribute__(method)(**kwargs) for reader in self.readers]

    def _get(self, attr):
        """Get value of *attr* for all readers."""
        return [reader.__getattribute__(attr) for reader in self.readers]

    def _get_same(self, attr):
        """Verify that *attr* has the same value for all readers and return value.

        :Arguments: *attr* attribute name
        :Returns: common value of the attribute
        :Raises: :Exc:`ValueError` if not all readers have the same value
        """
        values = np.array(self._get(attr))
        value = values[0]
        if not np.all(values == value):
            bad_traj = np.array([self.get_flname(fn) for fn in self.filenames])[values != value]
            raise ValueError("The following trajectories do not have the correct %s "
                             " (%d):\n%r" % (attr, value, bad_traj))
        return value

    def __activate_reader(self, i):
        """Make reader *i* the active reader."""
        # private method, not to be used by user to avoid a total mess
        if i < 0 or i >= len(self.readers):
            raise IndexError("Reader index must be 0 <= i < %d" % len(self.readers))
        self.__active_reader_index = i

    @property
    def active_reader(self):
        """Reader instance from which frames are being read."""
        return self.readers[self.__active_reader_index]

    def _read_frame(self, frame):
        """Position trajectory at frame index *frame* and return :class:`Timestep`.

        The frame is translated to the corresponding reader and local
        frame index and the Timestep instance in
        :attr:`ChainReader.ts` is updated.

        .. Note::

           *frame* is 0-based, i.e. the first frame in the trajectory is
           accessed with *frame* = 0.

        .. SeeAlso:: :meth:`~ChainReader._get_local_frame`.
        """
        i, f = self._get_local_frame(frame)
        # seek to (1) reader i and (2) frame f in trajectory i
        self.__activate_reader(i)
        self.active_reader[f]  # rely on reader to implement __getitem__()
        # update Timestep
        self.ts = self.active_reader.ts
        self.ts.frame = frame  # continuous frames, 0-based
        return self.ts

    def _chained_iterator(self):
        """Iterator that presents itself as a chained trajectory."""
        self._rewind()  # must rewind all readers
        readers = itertools.chain(*self.readers)
        for frame, ts in enumerate(readers):
            ts.frame = frame  # fake continuous frames, 0-based
            self.ts = ts
            # make sure that the active reader is in sync
            i, f = self._get_local_frame(frame)  # uses 0-based frames!
            self.__activate_reader(i)
            yield ts

    def _read_next_timestep(self, ts=None):
        self.ts = self.__chained_trajectories_iter.next()
        return self.ts

    def rewind(self):
        """Set current frame to the beginning."""
        self._rewind()
        self.__chained_trajectories_iter = self._chained_iterator()
        self.ts = self.__chained_trajectories_iter.next()  # set time step to frame 1

    def _rewind(self):
        """Internal method: Rewind trajectories themselves and trj pointer."""
        self._apply('rewind')
        self.__activate_reader(0)

    def close(self):
        self._apply('close')

    def __iter__(self):
        """Generator for all frames, starting at frame 1."""
        self._rewind()
        self.__chained_trajectories_iter = self._chained_iterator()  # start from first frame
        for ts in self.__chained_trajectories_iter:
            yield ts

    def get_flname(self, filename):  # retrieve the actual filename of the list element
        return filename[0] if isinstance(filename, tuple) else filename

    def __repr__(self):
        return "< %s %r with %d frames of %d atoms>" % \
               (self.__class__.__name__,
               [os.path.basename(self.get_flname(fn)) for fn in self.filenames],
               self.numframes, self.numatoms)


class Writer(IObase):
    """Base class for trajectory writers.

    See Trajectory API definition in :mod:`MDAnalysis.coordinates.__init__` for
    the required attributes and methods.
    """

    def convert_dimensions_to_unitcell(self, ts):
        """Read dimensions from timestep *ts* and return appropriate unitcell.

        The default is to return ``[A,B,C,alpha,beta,gamma]``; if this
        is not appropriate then this method has to be overriden.
        """
        #raise NotImplementedError("Writer.convert_dimensions_to_unitcell(): Override in the specific writer: [A,B,C,alpha,beta,gamma] --> native")
        # override if the native trajectory format does NOT use [A,B,C,alpha,beta,gamma]
        lengths, angles = ts.dimensions[:3], ts.dimensions[3:]
        self.convert_pos_to_native(lengths)
        return np.concatenate([lengths, angles])

    def write(self, obj):
        """Write current timestep, using the supplied *obj*.

        The argument should be a :class:`~MDAnalysis.core.AtomGroup.AtomGroup` or
        a :class:`~MDAnalysis.Universe` or a :class:`Timestep` instance.

        .. Note::

           The size of the *obj* must be the same as the number of atom
           provided when setting up the trajectory.
        """
        if isinstance(obj, Timestep):
            ts = obj
        else:
            try:
                ts = obj.ts
            except AttributeError:
                try:
                    # special case: can supply a Universe, too...
                    ts = obj.trajectory.ts
                except AttributeError:
                    raise TypeError("No Timestep found in obj argument")
        return self.write_next_timestep(ts)

    def __del__(self):
        self.close()

    def __repr__(self):
        try:
            return "< %s %r for %d atoms >" % (self.__class__.__name__, self.filename, self.numatoms)
        except (TypeError, AttributeError):
            # no trajectory loaded yet or a Writer that does not need e.g. self.numatoms
            return "< %s %r >" % (self.__class__.__name__, self.filename)

    def has_valid_coordinates(self, criteria, x):
        """Returns ``True`` if all values are within limit values of their formats.

        Due to rounding, the test is asymmetric (and *min* is supposed to be negative):

           min < x <= max

        :Arguments:
            *criteria*
               dictionary containing the *max* and *min* values in native units
            *x*
               :class:`np.ndarray` of ``(x, y, z)`` coordinates of atoms selected to be written out.
        :Returns: boolean
        """
        x = np.ravel(x)
        return np.all(criteria["min"] < x) and np.all(x <= criteria["max"])

        # def write_next_timestep(self, ts=None)

class SingleFrameReader(ProtoReader):
    """Base class for Readers that only have one frame.

    To use this base class, define the method :meth:`_read_first_frame` to
    read from file `self.filename`.  This should populate the attribute
    `self.ts` with a :class:`Timestep` object.

    .. versionadded:: 0.10.0
    .. versionchanged:: 0.11.0
       Added attribute "_ts_kwargs" for subclasses
       Keywords "dt" and "time_offset" read into _ts_kwargs
    """
    _err = "{0} only contains a single frame"

    def __init__(self, filename, convert_units=None, **kwargs):
        self.filename = filename
        if convert_units is None:
            convert_units = flags['convert_lengths']
        self.convert_units = convert_units

        self.numframes = 1

        ts_kwargs = {}
        for att in ('dt', 'time_offset'):
            try:
                val = kwargs[att]
            except KeyError:
                pass
            else:
                ts_kwargs[att] = val

        self._ts_kwargs = ts_kwargs
        self._read_first_frame()

    def _read_first_frame(self):  # pragma: no cover
        # Override this in subclasses to create and fill a Timestep
        pass

    def rewind(self):
        pass

    def _reopen(self):
        pass

    def next(self):
        raise IOError(self._err.format(self.__class__.__name__))

    def __iter__(self):
        yield self.ts
        raise StopIteration

    def _read_frame(self, frame):
        if frame != 0:
            raise IndexError(self._err.format(self.__class__.__name__))

        return self.ts

    def close(self):
        # all single frame readers should use context managers to access
        # self.filename. Explicitly setting it to the null action in case
        # the IObase.close method is ever changed from that.
        pass
