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

import MDAnalysis
from MDAnalysis.tests.datafiles import PSF, DCD, PDB_small, GRO, TRR, \
    merge_protein, merge_water, merge_ligand, \
    TRZ, TRZ_psf, PSF_notop, PSF_BAD, unordered_res, \
    XYZ_mini, two_water_gro, two_water_gro_nonames
import MDAnalysis.core.AtomGroup
from MDAnalysis.core.AtomGroup import Atom, AtomGroup, asUniverse
from MDAnalysis import NoDataError

import numpy
from numpy.testing import *
from numpy import array, float32, rad2deg
from nose.plugins.attrib import attr

import os
import tempfile
import itertools

from MDAnalysisTests.plugins.knownfailure import knownfailure


class TestAtom(TestCase):
    """Tests of Atom."""

    def setUp(self):
        """Set up the standard AdK system in implicit solvent."""
        self.universe = MDAnalysis.Universe(PSF, DCD)
        self.atom = self.universe.atoms[1000]  # Leu67:CG
        self.known_pos = array([3.94543672, -12.4060812, -7.26820087], dtype=float32)

    def tearDown(self):
        del self.universe
        del self.atom
        del self.known_pos

    def test_attributes_names(self):
        a = self.atom
        assert_equal(a.name, 'CG')
        assert_equal(a.resname, 'LEU')

    def test_attributes_pos(self):
        # old pos property
        assert_almost_equal(self.atom.pos, self.known_pos)

        def set_pos():
            self.atom.pos = self.known_pos + 3.14

        assert_raises(AttributeError, set_pos)

    def test_attributes_positions(self):
        a = self.atom
        # new position property (mutable)
        assert_almost_equal(a.position, self.known_pos)
        pos = a.position + 3.14
        a.position = pos
        assert_almost_equal(a.position, pos)

    def test_atom_selection(self):
        asel = self.universe.selectAtoms('atom 4AKE 67 CG').atoms[0]
        assert_equal(self.atom, asel)

    def test_hierarchy(self):
        u = self.universe
        a = self.atom
        assert_equal(a.segment, u.s4AKE)
        assert_equal(a.residue, u.residues[66])

    def test_bad_add(self):
        def bad_add():
            return self.atom + 1

        assert_raises(TypeError, bad_add)

    def test_add_AG(self):
        ag = self.universe.atoms[:2]

        ag2 = self.atom + ag

        for at in [self.atom, ag[0], ag[1]]:
            assert_equal(at in ag2, True)

    def test_no_velo(self):
        def lookup_velo():
            return self.atom.velocity

        assert_raises(NoDataError, lookup_velo)

    def test_atom_centroid(self):
        assert_equal(self.atom.position, self.atom.centroid())

    def test_no_uni(self):
        at = Atom(1, 'dave', 'C', 'a', 1, 1, 0.1, 0.0)

        def lookup_uni(a):
            return a.universe

        assert_raises(AttributeError, lookup_uni, at)

    def test_bonded_atoms(self):
        at = self.universe.atoms[0]
        ref = [b.partner(at) for b in at.bonds]
        assert_equal(ref, list(at.bonded_atoms))


class TestAtomNoForceNoVel(TestCase):
    def setUp(self):
        self.u = MDAnalysis.Universe(XYZ_mini)
        self.a = self.u.atoms[0]

    def tearDown(self):
        del self.u

    def test_velocity_fail(self):
        assert_raises(NoDataError, getattr, self.a, 'velocity')

    def test_force_fail(self):
        assert_raises(NoDataError, getattr, self.a, 'force')

    def test_velocity_set_fail(self):
        assert_raises(NoDataError, setattr, self.a, 'velocity', [1.0, 1.0, 1.0])

    def test_force_set_fail(self):
        assert_raises(NoDataError, setattr, self.a, 'force', [1.0, 1.0, 1.0])


class TestAtomGroup(TestCase):
    """Tests of AtomGroup; selections are tested separately."""
    # all tests are done with the AdK system (PSF and DCD)
    # sequence: http://www.uniprot.org/uniprot/P69441.fasta
    # >sp|P69441|KAD_ECOLI Adenylate kinase OS=Escherichia coli (strain K12) GN=adk PE=1 SV=1
    ref_adk_sequence = """\
       MRIILLGAPGAGKGTQAQFIMEKYGIPQISTGDMLRAAVKSGSELGKQAKDIMDAGKLVT
       DELVIALVKERIAQEDCRNGFLLDGFPRTIPQADAMKEAGINVDYVLEFDVPDELIVDRI
       VGRRVHAPSGRVYHVKFNPPKVEGKDDVTGEELTTRKDDQEETVRKRLVEYHQMTAPLIG
       YYSKEAEAGNTKYAKVDGTKPVAEVRADLEKILG""".translate(None, " \n\t")

    def setUp(self):
        """Set up the standard AdK system in implicit solvent."""
        self.universe = MDAnalysis.Universe(PSF, DCD)
        self.ag = self.universe.atoms  # prototypical AtomGroup
        self.dih_prec = 2

    def test_newAtomGroup(self):
        newag = MDAnalysis.core.AtomGroup.AtomGroup(self.ag[1000:2000:200])
        assert_equal(type(newag), type(self.ag), "Failed to make a new AtomGroup: type mismatch")
        assert_equal(newag.numberOfAtoms(), len(self.ag[1000:2000:200]))
        assert_equal(newag.numberOfResidues(), 5)
        assert_almost_equal(newag.totalMass(), 40.044999999999995)  # check any special method

    def test_getitem_int(self):
        assert_equal(self.universe.atoms[0], self.universe.atoms._atoms[0])

    def test_getitem_slice(self):
        assert_equal(self.universe.atoms[0:4]._atoms, self.universe.atoms._atoms[:4])

    def test_getitem_slice2(self):
        assert_equal(self.universe.atoms[0:8:2]._atoms, self.universe.atoms._atoms[0:8:2])

    def test_getitem_str(self):
        ag1 = self.universe.atoms['HT1']
        # selectAtoms always returns an AtomGroup even if single result
        ag2 = self.universe.selectAtoms('name HT1')[0]
        assert_equal(ag1, ag2)

    def test_getitem_list(self):
        sel = [0, 1, 4]
        ag1 = self.universe.atoms[sel]
        ag2 = AtomGroup([self.universe.atoms[i] for i in sel])
        assert_equal(ag1._atoms, ag2._atoms)

    def test_getitem_nparray(self):
        sel = numpy.arange(5)
        ag1 = self.universe.atoms[sel]
        ag2 = AtomGroup([self.universe.atoms[i] for i in sel])
        assert_equal(ag1._atoms, ag2._atoms)

    def test_getitem_TE(self):
        d = {'A': 1}
        assert_raises(TypeError, self.universe.atoms.__getitem__, d)

    def test_bad_make(self):
        assert_raises(TypeError, AtomGroup, ['these', 'are', 'not', 'atoms'])

    def test_numberOfAtoms(self):
        assert_equal(self.ag.numberOfAtoms(), 3341)

    def test_numberOfResidues(self):
        assert_equal(self.ag.numberOfResidues(), 214)

    def test_numberOfSegments(self):
        assert_equal(self.ag.numberOfSegments(), 1)

    def test_len(self):
        """testing that len(atomgroup) == atomgroup.numberOfAtoms()"""
        assert_equal(len(self.ag), self.ag.numberOfAtoms(), "len and numberOfAtoms() disagree")

    def test_centerOfGeometry(self):
        assert_array_almost_equal(self.ag.centerOfGeometry(),
                                  array([-0.04223963, 0.0141824, -0.03505163], dtype=float32))

    def test_centerOfMass(self):
        assert_array_almost_equal(self.ag.centerOfMass(),
                                  array([-0.01094035, 0.05727601, -0.12885778]))

    def test_coordinates(self):
        assert_array_almost_equal(self.ag.coordinates()[1000:2000:200],
                                  array(
                                      [
                                          [3.94543672, -12.4060812, -7.26820087],
                                          [13.21632767, 5.879035, -14.67914867],
                                          [12.07735443, -9.00604534, 4.09301519],
                                          [11.35541916, 7.0690732, -0.32511973],
                                          [-13.26763439, 4.90658951, 10.6880455]], dtype=float32))

    def test_principalAxes(self):
        assert_array_almost_equal(self.ag.principalAxes(),
                                  array([
                                      [-9.99925632e-01, 1.21546132e-02, 9.98264877e-04],
                                      [1.20986911e-02, 9.98951474e-01, -4.41539838e-02],
                                      [1.53389276e-03, 4.41386224e-02, 9.99024239e-01]]))

    def test_totalCharge(self):
        assert_almost_equal(self.ag.totalCharge(), -4.0)

    def test_totalMass(self):
        assert_almost_equal(self.ag.totalMass(), 23582.043)

    def test_indices_ndarray(self):
        assert_equal(isinstance(self.ag.indices(), numpy.ndarray), True)

    def test_indices(self):
        assert_array_equal(self.ag.indices()[:5], array([0, 1, 2, 3, 4]))

    def test_resids_ndarray(self):
        assert_equal(isinstance(self.ag.resids(), numpy.ndarray), True)

    def test_resids(self):
        assert_array_equal(self.ag.resids(), numpy.arange(1, 215))

    def test_resnums_ndarray(self):
        assert_equal(isinstance(self.ag.resnums(), numpy.ndarray), True)

    def test_resnums(self):
        assert_array_equal(self.ag.resids(), numpy.arange(1, 215))

    def test_resnames_ndarray(self):
        assert_equal(isinstance(self.ag.resnames(), numpy.ndarray), True)

    def test_resnames(self):
        resnames = self.ag.resnames()
        assert_array_equal(resnames[0:3], numpy.array(["MET", "ARG", "ILE"]))

    def test_names_ndarray(self):
        assert_equal(isinstance(self.ag.names(), numpy.ndarray), True)

    def test_names(self):
        names = self.ag.names()
        assert_array_equal(names[0:3], numpy.array(["N", "HT1", "HT2"]))

    def test_segids_ndarray(self):
        assert_equal(isinstance(self.ag.segids(), numpy.ndarray), True)

    def test_segids(self):
        segids = self.ag.segids()
        assert_array_equal(segids[0], numpy.array(["4AKE"]))

    def test_masses_ndarray(self):
        assert_equal(isinstance(self.ag.masses(), numpy.ndarray), True)

    def test_masses(self):
        masses = self.ag.masses()
        assert_array_equal(masses[0:3], numpy.array([14.007, 1.008, 1.008]))

    def test_charges_ndarray(self):
        assert_equal(isinstance(self.ag.charges(), numpy.ndarray), True)

    def test_charges(self):
        assert_array_almost_equal(self.ag.charges()[1000:2000:200],
                                  array([-0.09, 0.09, -0.47, 0.51, 0.09]))

    def test_radii_ndarray(self):
        assert_equal(isinstance(self.ag.radii(), numpy.ndarray), True)

    def test_radii(self):
        radii = self.ag.radii()
        assert_array_equal(radii[0:3], numpy.array([None, None, None]))

    def test_bfactors_ndarray(self):
        assert_equal(isinstance(self.ag.bfactors, numpy.ndarray), True)

    def test_bfactors(self):
        bfactors = self.ag.bfactors  # property, not method!
        assert_array_equal(bfactors[0:3], numpy.array([None, None, None]))

    def test_sequence_string(self):
        p = self.universe.selectAtoms("protein")
        assert_equal(p.sequence(format="string"), self.ref_adk_sequence)

    def test_sequence_SeqRecord(self):
        p = self.universe.selectAtoms("protein")
        s = p.sequence(format="SeqRecord",
                       id="P69441", name="KAD_ECOLI Adenylate kinase",
                       description="EcAdK from pdb 4AKE")
        assert_equal(s.id, "P69441")
        assert_equal(s.seq.tostring(), self.ref_adk_sequence)

    def test_sequence_SeqRecord_default(self):
        p = self.universe.selectAtoms("protein")
        s = p.sequence(id="P69441", name="KAD_ECOLI Adenylate kinase",
                       description="EcAdK from pdb 4AKE")
        assert_equal(s.id, "P69441")
        assert_equal(s.seq.tostring(), self.ref_adk_sequence)

    def test_sequence_Seq(self):
        p = self.universe.selectAtoms("protein")
        s = p.sequence(format="Seq")
        assert_equal(s.tostring(), self.ref_adk_sequence)

    def test_sequence_nonIUPACresname(self):
        """test_sequence_nonIUPACresname: non recognized amino acids raise ValueError"""
        # fake non-IUPAC residue name for this test
        self.universe.selectAtoms("resname MET").set_resname("MSE")
        self.universe.atoms._rebuild_caches()
        def wrong_res():
            self.universe.atoms.sequence()
        assert_raises(ValueError, wrong_res)

    def test_no_uni(self):
        at1 = Atom(1, 'dave', 'C', 'a', 1, 1, 0.1, 0.0)
        at2 = Atom(2, 'dave', 'C', 'a', 1, 1, 0.1, 0.0)
        ag = AtomGroup([at1, at2])
        assert_equal(ag.universe, None)

    def test_bad_add_AG(self):
        def bad_add():
            return self.ag + [1, 2, 3]
        assert_raises(TypeError, bad_add)

    def test_bool_false(self):
        # Issue #304
        ag = AtomGroup([])
        assert_equal(bool(ag), False)

    def test_bool_true(self):
        # Issue #304
        ag = self.universe.atoms[:3]
        assert_equal(bool(ag), True)

    def test_repr(self):
        # Should make sure that the user facing info stays as expected
        assert_equal(repr(self.ag), "<AtomGroup with 3341 atoms>")

    ## Issue 202 following 4 tests
    @knownfailure()
    def test_set_resnum_single(self):
        ag = self.universe.atoms[:3]
        new = 5
        ag.set_resnum(new)
        for at in ag:
            assert_equal(at.resnum, new)
        assert_equal(all(ag.resnums() == new), True)

    @knownfailure()
    def test_set_resnum_many(self):
        ag = self.universe.atoms[:3]
        new = [22, 23, 24]
        ag.set_resnum(new)
        for at, v in zip(ag, new):
            assert_equal(at.resnum, v)
        assert_equal(all(ag.resnums() == new), True)

    def test_set_resname_single(self):
        ag = self.universe.atoms[:3]
        new = 'abc'
        ag.set_resname(new)
        for at in ag:
            assert_equal(at.resname, new)
        assert_equal(all(ag.resnames() == new), True)

    @knownfailure()
    def test_set_resname_many(self):
        ag = self.universe.atoms[:3]
        new = ['aa', 'bb', 'cc']
        ag.set_resname(new)
        for at, v in zip(ag, new):
            assert_equal(at.resname, v)
        assert_equal(all(ag.resnames() == new), True)

    # TODO: add all other methods except selectAtoms(), see test_atomselections.py
    def test_set_charge(self):
        # Charges are initially 0
        at1 = Atom(1, 'dave', 'C', 'a', 1, 1, 0.1, 0.0)
        at2 = Atom(2, 'dave', 'C', 'a', 1, 1, 0.1, 0.0)
        ag = AtomGroup([at1, at2])

        charges = [1.0, 2.0]
        ag.set_charge(charges)
        for at, val in zip(ag, charges):
            assert_equal(at.charge, val)

    def test_set_radius(self):
        at1 = Atom(1, 'dave', 'C', 'a', 1, 1, 0.1, 0.0)
        at2 = Atom(2, 'dave', 'C', 'a', 1, 1, 0.1, 0.0)
        ag = AtomGroup([at1, at2])

        radii = [1.0, 2.0]
        ag.set_radius(radii)
        for at, val in zip(ag, radii):
            assert_equal(at.radius, val)

    def test_set_bfactor(self):
        at1 = Atom(1, 'dave', 'C', 'a', 1, 1, 0.1, 0.0)
        at2 = Atom(2, 'dave', 'C', 'a', 1, 1, 0.1, 0.0)
        ag = AtomGroup([at1, at2])

        bfacs = [1.0, 2.0]
        ag.set_bfactor(bfacs)
        for at, val in zip(ag, bfacs):
            assert_equal(at.bfactor, val)

    # add new methods here...
    def test_packintobox_badshape(self):
        ag = self.universe.atoms[:10]
        box = numpy.zeros(9, dtype=numpy.float32).reshape(3, 3)

        def badpack(a):
            return a.packIntoBox(box=box)

        assert_raises(ValueError, badpack, ag)

    def test_packintobox_noshape(self):
        ag = self.universe.atoms[:10]

        def badpack(a):
            return a.packIntoBox()

        assert_raises(ValueError, badpack, ag)

    def test_packintobox(self):
        """test AtomGroup.packIntoBox(): Tests application of periodic boundary conditions on coordinates

        Reference system doesn't have dimensions, so an arbitrary box is imposed on the system
        """
        u = self.universe
        u.trajectory.rewind()  # just to make sure...
        ag = u.atoms[1000:2000:200]

        ag.packIntoBox(box=numpy.array([5., 5., 5.], dtype=numpy.float32))  # Provide arbitrary box
        assert_array_almost_equal(ag.coordinates(),
                                  array(
                                      [
                                          [3.94543672, 2.5939188, 2.73179913],
                                          [3.21632767, 0.879035, 0.32085133],
                                          [2.07735443, 0.99395466, 4.09301519],
                                          [1.35541916, 2.0690732, 4.67488003],
                                          [1.73236561, 4.90658951, 0.6880455]], dtype=float32))

    def test_residues(self):
        u = self.universe
        assert_equal(u.residues[100]._atoms,
                     u.selectAtoms('resname ILE and resid 101')._atoms,
                     "Direct selection from residue group does not match expected I101.")

    def test_segments(self):
        u = self.universe
        assert_equal(u.segments.s4AKE._atoms,
                     u.selectAtoms('segid 4AKE')._atoms,
                     "Direct selection of segment 4AKE from segments failed.")

    def test_index_integer(self):
        u = self.universe
        a = u.atoms[100]
        assert_(isinstance(a, Atom), "integer index did not return Atom")

    def test_index_slice(self):
        u = self.universe
        a = u.atoms[100:200:10]
        assert_(isinstance(a, AtomGroup), "slice index did not return AtomGroup")

    def test_index_slice_empty(self):
        u = self.universe
        assert_array_equal(u.atoms[0:0], [], "making an empty AtomGroup failed")

    def test_index_advancedslice(self):
        u = self.universe
        aslice = [0, 10, 20, -1, 10]
        ag = u.atoms[aslice]
        assert_(isinstance(ag, AtomGroup),
                "advanced slicing does not produce a AtomGroup")
        assert_equal(ag[1], ag[-1], "advanced slicing does not preserve order")

    def test_boolean_indexing(self):
        # index an array with a sequence of bools
        # issue #282
        sel = numpy.array([True, False, True])
        ag = self.universe.atoms[10:13]
        ag2 = ag[sel]
        assert_equal(len(ag2), 2)
        for at in [ag[0], ag[2]]:
            assert_equal(at in ag2, True)

    def test_bool_IE(self):
        # indexing with empty list doesn't run foul of bool check
        sel = []
        ag = self.universe.atoms[10:30]
        ag2 = ag[sel]
        assert_equal(len(ag2), 0)

    def test_phi_selection(self):
        phisel = self.universe.s4AKE.r10.phi_selection()
        assert_equal(phisel.names(), ['C', 'N', 'CA', 'C'])
        assert_equal(phisel.resids(), [9, 10])
        assert_equal(phisel.resnames(), ['PRO', 'GLY'])

    def test_psi_selection(self):
        psisel = self.universe.s4AKE.r10.psi_selection()
        assert_equal(psisel.names(), ['N', 'CA', 'C', 'N'])
        assert_equal(psisel.resids(), [10, 11])
        assert_equal(psisel.resnames(), ['GLY', 'ALA'])

    def test_omega_selection(self):
        osel = self.universe.s4AKE.r8.omega_selection()
        assert_equal(osel.names(), ['CA', 'C', 'N', 'CA'])
        assert_equal(osel.resids(), [8, 9])
        assert_equal(osel.resnames(), ['ALA', 'PRO'])

    def test_chi1_selection(self):
        sel = self.universe.s4AKE.r13.chi1_selection()  # LYS
        assert_equal(sel.names(), ['N', 'CA', 'CB', 'CG'])
        assert_equal(sel.resids(), [13])
        assert_equal(sel.resnames(), ['LYS'])

    # Test failed selections of phi/psi/omega/chi1
    def test_phi_sel_fail(self):
        sel = self.universe.residues[0].phi_selection()
        assert_equal(sel, None)

    def test_psi_sel_fail(self):
        sel = self.universe.residues[-1].psi_selection()
        assert_equal(sel, None)

    def test_omega_sel_fail(self):
        sel = self.universe.residues[-1].omega_selection()
        assert_equal(sel, None)

    def test_ch1_sel_fail(self):
        sel = self.universe.s4AKE.r8.chi1_selection()
        assert_equal(sel, None)  # ALA

    def test_dihedral_phi(self):
        u = self.universe
        u.trajectory.rewind()  # just to make sure...
        phisel = u.s4AKE.r10.phi_selection()
        assert_almost_equal(phisel.dihedral(), -168.57384, self.dih_prec)

    def test_dihedral_psi(self):
        u = self.universe
        u.trajectory.rewind()  # just to make sure...
        psisel = u.s4AKE.r10.psi_selection()
        assert_almost_equal(psisel.dihedral(), -30.064838, self.dih_prec)

    def test_dihedral_omega(self):
        u = self.universe
        u.trajectory.rewind()  # just to make sure...
        osel = u.s4AKE.r8.omega_selection()
        assert_almost_equal(osel.dihedral(), -179.93439, self.dih_prec)

    def test_dihedral_chi1(self):
        u = self.universe
        u.trajectory.rewind()  # just to make sure...
        sel = u.s4AKE.r13.chi1_selection()  # LYS
        assert_almost_equal(sel.dihedral(), -58.428127, self.dih_prec)

    def test_dihedral_ValueError(self):
        """test that AtomGroup.dihedral() raises ValueError if not exactly 4 atoms given"""
        nodih = self.universe.selectAtoms("resid 3:10")
        assert_raises(ValueError, nodih.dihedral)
        nodih = self.universe.selectAtoms("resid 3:5")
        assert_raises(ValueError, nodih.dihedral)

    def test_improper(self):
        u = self.universe
        u.trajectory.rewind()  # just to make sure...
        peptbond = u.selectAtoms("atom 4AKE 20 C", "atom 4AKE 21 CA",
                                 "atom 4AKE 21 N", "atom 4AKE 21 HN")
        assert_almost_equal(peptbond.improper(), 168.52952575683594, self.dih_prec,
                            "Peptide bond improper dihedral for M21 calculated wrongly.")

    def test_dihedral_equals_improper(self):
        u = self.universe
        u.trajectory.rewind()  # just to make sure...
        peptbond = u.selectAtoms("atom 4AKE 20 C", "atom 4AKE 21 CA",
                                 "atom 4AKE 21 N", "atom 4AKE 21 HN")
        assert_equal(peptbond.improper(), peptbond.dihedral(),
                     "improper() and proper dihedral() give different results")

    def test_bond(self):
        self.universe.trajectory.rewind()  # just to make sure...
        sel2 = self.universe.s4AKE.r98.selectAtoms("name OE1", "name OE2")
        assert_almost_equal(sel2.bond(), 2.1210737228393555, 3,
                            "distance of Glu98 OE1--OE2 wrong")

    def test_bond_pbc(self):
        self.universe.trajectory.rewind()
        sel2 = self.universe.s4AKE.r98.selectAtoms("name OE1", "name OE2")
        assert_almost_equal(sel2.bond(pbc=True), 2.1210737228393555, 3,
                            "distance of Glu98 OE1--OE2 wrong")

    def test_bond_ValueError(self):
        ag = self.universe.atoms[:4]
        assert_raises(ValueError, ag.bond)

    def test_angle(self):
        self.universe.trajectory.rewind()  # just to make sure...
        sel3 = self.universe.s4AKE.r98.selectAtoms("name OE1", "name CD", "name OE2")
        assert_almost_equal(sel3.angle(), 117.46187591552734, 3,
                            "angle of Glu98 OE1-CD-OE2 wrong")

    def test_angle_ValueError(self):
        ag = self.universe.atoms[:2]
        assert_raises(ValueError, ag.angle)

    def test_shapeParameter(self):
        s = self.universe.s4AKE.shapeParameter()
        assert_almost_equal(s, 0.00240753939086033, 6)

    def test_asphericity(self):
        a = self.universe.s4AKE.asphericity()
        assert_almost_equal(a, 0.020227504542775828, 6)

    # TODO: tests for the coordinate manipulation methods
    # - transform
    # - translate
    # - rotate
    # - rotateby

    def test_positions(self):
        ag = self.universe.selectAtoms("bynum 12:42")
        pos = ag.positions + 3.14
        ag.positions = pos
        # should work
        assert_almost_equal(ag.coordinates(), pos,
                            err_msg="failed to update atoms 12:42 position to new position")
        def set_badarr(pos=pos):
            # create wrong size array
            badarr = numpy.random.random((pos.shape[0] - 1, pos.shape[1] - 1))
            ag.positions = badarr
        assert_raises(ValueError, set_badarr)

    def test_set_positions(self):
        ag = self.universe.selectAtoms("bynum 12:42")
        pos = ag.get_positions() + 3.14
        ag.set_positions(pos)
        assert_almost_equal(ag.coordinates(), pos,
                            err_msg="failed to update atoms 12:42 position to new position")

    def test_no_velocities_raises_NoDataError(self):
        def get_vel(ag=self.universe.selectAtoms("bynum 12:42")):
            v = ag.get_velocities()
        # trj has no velocities
        assert_raises(NoDataError, get_vel)

    def test_set_velocities_NoData(self):
        def set_vel():
            return self.universe.atoms[:2].set_velocities([0.2])
        assert_raises(NoDataError, set_vel)

    def test_get_forces_NoData(self):
        def get_for():
            return self.universe.atoms[:2].get_forces()
        assert_raises(NoDataError, get_for)

    def test_set_forces_NoData(self):
        def set_for():
            return self.universe.atoms[:2].set_forces([0.2])
        assert_raises(NoDataError, set_for)

    def test_set_resid(self):
        ag = self.universe.selectAtoms("bynum 12:42")
        resid = 999
        ag.set_resid(resid)
        # check individual atoms
        assert_equal([a.resid for a in ag],
                     resid * numpy.ones(ag.numberOfAtoms()),
                     err_msg="failed to set_resid atoms 12:42 to same resid")
        # check residues
        assert_equal(ag.resids(), 999 * numpy.ones(ag.numberOfResidues()),
                     err_msg="failed to set_resid of residues belonging to atoms 12:42 to same resid")

    def test_set_names(self):
        ag = self.universe.atoms[:2]
        names = ['One', 'Two']
        ag.set_name(names)
        for a, b in zip(ag, names):
            assert_equal(a.name, b)

    def test_set_resids(self):
        """test_set_resid: set AtomGroup resids on a per-atom basis"""
        ag = self.universe.selectAtoms("bynum 12:42")
        resids = numpy.array([a.resid for a in ag]) + 1000
        ag.set_resid(resids)
        # check individual atoms
        assert_equal([a.resid for a in ag], resids,
                     err_msg="failed to set_resid atoms 12:42 to resids {0}".format(resids))
        # check residues
        assert_equal(ag.resids(), numpy.unique(resids),
                     err_msg="failed to set_resid of residues belonging to atoms 12:42 to same resid")

    def test_merge_residues(self):
        ag = self.universe.selectAtoms("resid 12:14")
        nres_old = self.universe.atoms.numberOfResidues()
        natoms_old = ag.numberOfAtoms()
        ag.set_resid(12)  # merge all into one with resid 12
        nres_new = self.universe.atoms.numberOfResidues()
        r_merged = self.universe.selectAtoms("resid 12:14").residues
        natoms_new = self.universe.selectAtoms("resid 12").numberOfAtoms()
        assert_equal(len(r_merged), 1, err_msg="set_resid failed to merge residues: merged = {0}".format(r_merged))
        assert_equal(nres_new, nres_old - 2,
                     err_msg="set_resid failed to merge residues: merged = {0}".format(r_merged))
        assert_equal(natoms_new, natoms_old, err_msg="set_resid lost atoms on merge".format(r_merged))

    def test_set_mass(self):
        ag = self.universe.selectAtoms("bynum 12:42 and name H*")
        mass = 2.0
        ag.set_mass(mass)
        # check individual atoms
        assert_equal([a.mass for a in ag],
                     mass * numpy.ones(ag.numberOfAtoms()),
                     err_msg="failed to set_mass H* atoms in resid 12:42 to {0}".format(mass))

    def test_set_segid(self):
        u = self.universe
        u.selectAtoms("(resid 1-29 or resid 60-121 or resid 160-214)").set_segid("CORE")
        u.selectAtoms("resid 122-159").set_segid("LID")
        u.selectAtoms("resid 30-59").set_segid("NMP")
        assert_equal(u.atoms.segids(), ["CORE", "NMP", "CORE", "LID", "CORE"],
                     err_msg="failed to change segids = {0}".format(u.atoms.segids()))

    def test_wronglen_set(self):
        """Give the setter function a list of wrong length"""
        assert_raises(ValueError, self.ag.set_mass, [0.1, 0.2])

    def test_split_atoms(self):
        ag = self.universe.selectAtoms("resid 1:50 and not resname LYS and (name CA or name CB)")
        sg = ag.split("atom")
        assert_equal(len(sg), len(ag))
        for g, ref_atom in itertools.izip(sg, ag):
            atom = g[0]
            assert_equal(len(g), 1)
            assert_equal(atom.name, ref_atom.name)
            assert_equal(atom.resid, ref_atom.resid)

    def test_split_residues(self):
        ag = self.universe.selectAtoms("resid 1:50 and not resname LYS and (name CA or name CB)")
        sg = ag.split("residue")
        assert_equal(len(sg), len(ag.resids()))
        for g, ref_resname in itertools.izip(sg, ag.resnames()):
            if ref_resname == "GLY":
                assert_equal(len(g), 1)
            else:
                assert_equal(len(g), 2)
            for atom in g:
                assert_equal(atom.resname, ref_resname)

    def test_split_segments(self):
        ag = self.universe.selectAtoms("resid 1:50 and not resname LYS and (name CA or name CB)")
        sg = ag.split("segment")
        assert_equal(len(sg), len(ag.segids()))
        for g, ref_segname in itertools.izip(sg, ag.segids()):
            for atom in g:
                assert_equal(atom.segid, ref_segname)

    # instant selectors
    @attr("issue")
    def test_nonexistent_instantselector_raises_AttributeError(self):
        def access_nonexistent_instantselector():
            self.universe.atoms.NO_SUCH_ATOM
        assert_raises(AttributeError, access_nonexistent_instantselector)

class TestAtomGroupNoTop(TestCase):
    def setUp(self):
        self.u = MDAnalysis.Universe(PSF_notop, DCD)
        self.ag = self.u.atoms[:10]

    def tearDown(self):
        del self.u
        del self.ag

    def test_nobonds(self):
        assert_equal(self.ag.bonds, [])

    def test_noangles(self):
        assert_equal(self.ag.angles, [])

    def test_notorsions(self):
        assert_equal(self.ag.torsions, [])

    def test_noimps(self):
        assert_equal(self.ag.impropers, [])

    # Because I'm messing with atom info, I've put these here separated from other tests
    def test_clear_cache(self):
        self.ag._clear_caches()

        assert_equal(self.ag._cache, dict())

    def test_rebuild_cache_residues(self):
        assert_equal(len(self.ag.residues), 1)

        # Mess with stuff, add a different residues and segment for the first atom
        self.ag[0].residue = self.u.atoms[100].residue

        # There's actually 2 residues now, but because of cache this isn't detected
        assert_equal(len(self.ag.residues), 1)

        # After cache rebuild second residue is finally seen
        self.ag._rebuild_caches()
        assert_equal(len(self.ag.residues), 2)

    def test_rebuild_cache_segments(self):
        # This test is similar to above, but a second segment has to be taken from a new universe
        assert_equal(len(self.ag.segments), 1)

        u2 = MDAnalysis.Universe(PSF_notop, DCD)
        self.ag[0].segment = u2.atoms[0].segment

        assert_equal(len(self.ag.segments), 1)
        self.ag._rebuild_caches()
        assert_equal(len(self.ag.segments), 2)

    def test_atom_cachesize_change(self):
        # By default 10,000 atoms are required to necessitate cache lookup, we can change this though
        ag = self.u.atoms[:100]
        # run a __contains__ query
        val = self.u.atoms[10] in ag
        # Check that cache wasn't used
        assert_equal('atoms' in ag._cache, False)
        ag._atomcache_size = 50  # now will make cache if size > 50
        # Run another query
        val = self.u.atoms[10] in ag
        # Check if cache was built this time
        assert_equal('atoms' in ag._cache, True)

    def test_atomcache_use(self):
        # Tests that lookup with 'atoms' cache works
        ag = self.u.atoms[:100]
        ag._atomcache_size = 50
        assert_equal(self.u.atoms[50] in ag, True)

    def test_rebuild_atomcache_no(self):
        # Don't always add atoms into cache
        ag = self.u.atoms[:100]
        ag._rebuild_caches()
        assert_equal('atoms' in ag._cache, False)

    def test_rebuild_atomcache(self):
        # Tests that 'atoms' is built into cache if size is enough
        ag = self.u.atoms[:100]
        ag._atomcache_size = 50
        ag._rebuild_caches()
        assert_equal('atoms' in ag._cache, True)

    def test_set_dimensions(self):
        u = MDAnalysis.Universe(PSF, DCD)
        box = numpy.array([10, 11, 12, 90, 90, 90])
        u.atoms.dimensions = numpy.array([10, 11, 12, 90, 90, 90])
        assert_allclose(u.dimensions, box)
        assert_allclose(u.atoms.dimensions, box)


class TestUniverseSetTopology(TestCase):
    """Tests setting of bonds/angles/torsions/impropers from Universe."""

    def setUp(self):
        self.u = MDAnalysis.Universe(PSF, DCD)

    def tearDown(self):
        del self.u

    def test_set_bonds(self):
        assert_equal(len(self.u.bonds), 3365)
        assert_equal(len(self.u.atoms[0].bonds), 4)

        self.u.bonds = []

        assert_equal(len(self.u.bonds), 0)
        assert_equal(len(self.u.atoms[0].bonds), 0)

    def test_set_angles(self):
        assert_equal(len(self.u.angles), 6123)
        assert_equal(len(self.u.atoms[0].angles), 9)

        self.u.angles = []

        assert_equal(len(self.u.angles), 0)
        assert_equal(len(self.u.atoms[0].angles), 0)

    def test_set_torsions(self):
        assert_equal(len(self.u.torsions), 8921)
        assert_equal(len(self.u.atoms[0].torsions), 14)

        self.u.torsions = []

        assert_equal(len(self.u.torsions), 0)
        assert_equal(len(self.u.atoms[0].torsions), 0)

    def test_set_impropers(self):
        assert_equal(len(self.u.impropers), 541)
        assert_equal(len(self.u.atoms[4].impropers), 1)

        self.u.impropers = []

        assert_equal(len(self.u.impropers), 0)
        assert_equal(len(self.u.atoms[4].impropers), 0)

    # Test deleting topology information
    # In general, access it to make sure it's built
    # Assert it's in cache
    # Delete
    # Assert it's not in cache
    def test_bonds_delete(self):
        bg = self.u.bonds
        abg = self.u.atoms[0].bonds

        assert_equal('bonds' in self.u._cache, True)
        assert_equal('bondDict' in self.u._cache, True)

        del self.u.bonds

        assert_equal('bonds' in self.u._cache, False)
        assert_equal('bondDict' in self.u._cache, False)

    def test_angles_delete(self):
        bg = self.u.angles
        abg = self.u.atoms[0].angles

        assert_equal('angles' in self.u._cache, True)
        assert_equal('angleDict' in self.u._cache, True)

        del self.u.angles

        assert_equal('angles' in self.u._cache, False)
        assert_equal('angleDict' in self.u._cache, False)

    def test_torsions_delete(self):
        bg = self.u.torsions
        abg = self.u.atoms[0].torsions

        assert_equal('torsions' in self.u._cache, True)
        assert_equal('torsionDict' in self.u._cache, True)

        del self.u.torsions

        assert_equal('torsions' in self.u._cache, False)
        assert_equal('torsionDict' in self.u._cache, False)

    def test_impropers_delete(self):
        bg = self.u.impropers
        abg = self.u.atoms[0].impropers

        assert_equal('impropers' in self.u._cache, True)
        assert_equal('improperDict' in self.u._cache, True)

        del self.u.impropers

        assert_equal('impropers' in self.u._cache, False)
        assert_equal('improperDict' in self.u._cache, False)


class TestResidue(TestCase):
    def setUp(self):
        self.universe = MDAnalysis.Universe(PSF, DCD)
        self.res = self.universe.residues[100]

    def test_type(self):
        assert_equal(type(self.res), MDAnalysis.core.AtomGroup.Residue)
        assert_equal(self.res.name, "ILE")
        assert_equal(self.res.id, 101)

    def test_index(self):
        atom = self.res[2]
        assert_equal(type(atom), MDAnalysis.core.AtomGroup.Atom)
        assert_equal(atom.name, "CA")
        assert_equal(atom.number, 1522)
        assert_equal(atom.resid, 101)

    def test_slicing(self):
        atoms = self.res[2:10:2]
        assert_equal(len(atoms), 4)
        assert_equal(type(atoms), MDAnalysis.core.AtomGroup.AtomGroup)

    def test_advanced_slicing(self):
        atoms = self.res[[0, 2, -2, -1]]
        assert_equal(len(atoms), 4)
        assert_equal(type(atoms), MDAnalysis.core.AtomGroup.AtomGroup)
        assert_equal(atoms.names(), ["N", "CA", "C", "O"])


class TestResidueGroup(TestCase):
    def setUp(self):
        """Set up the standard AdK system in implicit solvent."""
        self.universe = MDAnalysis.Universe(PSF, DCD)
        self.rg = self.universe.atoms.residues

    def test_newResidueGroup(self):
        """test that slicing a ResidueGroup returns a new ResidueGroup (Issue 135)"""
        rg = self.universe.atoms.residues
        newrg = rg[10:20:2]
        assert_equal(type(newrg), type(rg), "Failed to make a new ResidueGroup: type mismatch")
        assert_equal(len(newrg), len(rg[10:20:2]))

    def test_numberOfAtoms(self):
        assert_equal(self.rg.numberOfAtoms(), 3341)

    def test_numberOfResidues(self):
        assert_equal(self.rg.numberOfResidues(), 214)

    def test_len(self):
        """testing that len(residuegroup) == residuegroup.numberOfResidues()"""
        assert_equal(len(self.rg), self.rg.numberOfResidues(), "len and numberOfResidues() disagree")

    def test_set_resid(self):
        rg = self.universe.selectAtoms("bynum 12:42").residues
        resid = 999
        rg.set_resid(resid)
        # check individual atoms
        assert_equal([a.resid for a in rg.atoms],
                     resid * numpy.ones(rg.numberOfAtoms()),
                     err_msg="failed to set_resid atoms 12:42 to same resid")
        # check residues
        assert_equal(rg.resids(), resid * numpy.ones(rg.numberOfResidues()),
                     err_msg="failed to set_resid of residues belonging to atoms 12:42 to same resid")

    def test_set_resids(self):
        """test_set_resid: set ResidueGroup resids on a per-residue basis"""
        rg = self.universe.selectAtoms("resid 10:18").residues
        resids = numpy.array(rg.resids()) + 1000
        rg.set_resid(resids)
        # check individual atoms
        for r, resid in itertools.izip(rg, resids):
            assert_equal([a.resid for a in r.atoms],
                         resid * numpy.ones(r.numberOfAtoms()),
                         err_msg="failed to set_resid residues 10:18 to same resid in residue {0}\n"
                                 "(resids = {1}\nresidues = {2})".format(r, resids, rg))
        # check residues
        # NOTE: need to create a new selection because underlying Residue objects are not changed;
        #       only Atoms are changed, and Residues are rebuilt from Atoms.
        rgnew = self.universe.selectAtoms("resid 1010:1018").residues
        assert_equal(rgnew.resids(), numpy.unique(resids),
                     err_msg="failed to set_resid of residues belonging to residues 10:18 to new resids")

    def test_set_resids_updates_self(self):
        rg = self.universe.selectAtoms("resid 10:18").residues
        resids = numpy.array(rg.resids()) + 1000
        rg.set_resid(resids)
        #rgnew = self.universe.selectAtoms("resid 1000:1008").residues
        assert_equal(rg.resids(), numpy.unique(resids),
                     err_msg="old selection was not changed in place after set_resid")

    def test_set_resnum_single(self):
        rg = self.universe.residues[:3]
        new = 22
        rg.set_resnum(new)

        assert_equal(all(rg.resnums() == new), True)
        for r in rg:
            assert_equal(r.resnum, new)

    def test_set_resnum_many(self):
        rg = self.universe.residues[:3]
        new = [22, 23, 24]
        rg.set_resnum(new)

        assert_equal(all(rg.resnums() == new), True)
        for r, v in zip(rg, new):
            assert_equal(r.resnum, v)

    def test_set_resnum_ValueError(self):
        rg = self.universe.residues[:3]
        new = [22, 23, 24, 25]

        assert_raises(ValueError, rg.set_resnum, new)

    def test_set_resname_single(self):
        rg = self.universe.residues[:3]
        new = 'newname'

        rg.set_resname(new)
        assert_equal(all(rg.resnames() == new), True)
        for r in rg:
            assert_equal(r.name, new)

    def test_set_resname_many(self):
        rg = self.universe.residues[:3]
        new = ['a', 'b', 'c']
        rg.set_resname(new)

        assert_equal(all(rg.resnames() == new), True)
        for r, v in zip(rg, new):
            assert_equal(r.name, v)

    def test_set_resname_ValueError(self):
        rg = self.universe.residues[:3]
        new = ['a', 'b', 'c', 'd']

        assert_raises(ValueError, rg.set_resname, new)

    def test_merge_residues(self):
        rg = self.universe.selectAtoms("resid 12:14").residues
        nres_old = self.universe.atoms.numberOfResidues()
        natoms_old = rg.numberOfAtoms()
        rg.set_resid(12)  # merge all into one with resid 12
        nres_new = self.universe.atoms.numberOfResidues()
        r_merged = self.universe.selectAtoms("resid 12:14").residues
        natoms_new = self.universe.selectAtoms("resid 12").numberOfAtoms()
        assert_equal(len(r_merged), 1, err_msg="set_resid failed to merge residues: merged = {0}".format(r_merged))
        assert_equal(nres_new, nres_old - 2,
                     err_msg="set_resid failed to merge residues: merged = {0}".format(r_merged))
        assert_equal(natoms_new, natoms_old, err_msg="set_resid lost atoms on merge".format(r_merged))

        assert_equal(self.universe.residues.numberOfResidues(), self.universe.atoms.numberOfResidues(),
                     err_msg="Universe.residues and Universe.atoms.numberOfResidues() do not agree after residue "
                             "merge.")

    def test_set_mass(self):
        rg = self.universe.selectAtoms("bynum 12:42 and name H*").residues
        mass = 2.0
        rg.set_mass(mass)
        # check individual atoms
        assert_equal([a.mass for a in rg.atoms],
                     mass * numpy.ones(rg.numberOfAtoms()),
                     err_msg="failed to set_mass H* atoms in resid 12:42 to {0}".format(mass))


class TestSegment(TestCase):
    def setUp(self):
        self.universe = MDAnalysis.Universe(PSF, DCD)
        self.universe.residues[:100].set_segid("A")  # make up some segments
        self.universe.residues[100:150].set_segid("B")
        self.universe.residues[150:].set_segid("C")
        self.sB = self.universe.segments[1]

    def test_type(self):
        assert_equal(type(self.sB), MDAnalysis.core.AtomGroup.Segment)
        assert_equal(self.sB.name, "B")

    def test_index(self):
        s = self.sB
        res = s[5]
        assert_equal(type(res), MDAnalysis.core.AtomGroup.Residue)

    def test_slicing(self):
        res = self.sB[5:10]
        assert_equal(len(res), 5)
        assert_equal(type(res), MDAnalysis.core.AtomGroup.ResidueGroup)

    def test_advanced_slicing(self):
        res = self.sB[[3, 7, 2, 4]]
        assert_equal(len(res), 4)
        assert_equal(type(res), MDAnalysis.core.AtomGroup.ResidueGroup)

    def test_id(self):
        assert_equal(self.sB.name, self.sB.id)

    def test_set_id(self):
        # Test setting the name via the id attribute
        new = 'something'
        self.sB.id = new
        for val in [self.sB.id, self.sB.name]:
            assert_equal(val, new)


class TestSegmentGroup(TestCase):
    def setUp(self):
        """Set up the standard AdK system in implicit solvent."""
        self.universe = MDAnalysis.Universe(PSF, DCD)
        self.g = self.universe.atoms.segments

    def test_newSegmentGroup(self):
        """test that slicing a SegmentGroup returns a new SegmentGroup (Issue 135)"""
        g = self.universe.atoms.segments
        newg = g[:]
        assert_equal(type(newg), type(g), "Failed to make a new SegmentGroup: type mismatch")
        assert_equal(len(newg), len(g))

    def test_numberOfAtoms(self):
        assert_equal(self.g.numberOfAtoms(), 3341)

    def test_numberOfResidues(self):
        assert_equal(self.g.numberOfResidues(), 214)

    def test_set_resid(self):
        g = self.universe.selectAtoms("bynum 12:42").segments
        resid = 999
        g.set_resid(resid)
        # check individual atoms
        assert_equal([a.resid for a in g.atoms],
                     resid * numpy.ones(g.numberOfAtoms()),
                     err_msg="failed to set_resid for segment to same resid")
        # check residues
        assert_equal(g.resids(), resid * numpy.ones(g.numberOfResidues()),
                     err_msg="failed to set_resid of segments belonging to atoms 12:42 to same resid")

    def test_set_resids(self):
        g = self.universe.selectAtoms("resid 10:18").segments
        resid = 999
        g.set_resid(resid * numpy.ones(len(g)))
        # note: all is now one residue... not meaningful but it is the correct behaviour
        assert_equal(g.atoms.resids(), [resid],
                     err_msg="failed to set_resid  in Segment {0}".format(g))

    def test_set_segid(self):
        s = self.universe.selectAtoms('all').segments
        s.set_segid(['ADK'])
        assert_equal(self.universe.segments.segids(), ['ADK'],
                     err_msg="failed to set_segid on segments")

    def test_set_segid_updates_self(self):
        g = self.universe.selectAtoms("resid 10:18").segments
        g.set_segid('ADK')
        assert_equal(g.segids(), ['ADK'],
                     err_msg="old selection was not changed in place after set_segid")

    def test_set_mass(self):
        g = self.universe.selectAtoms("bynum 12:42 and name H*").segments
        mass = 2.0
        g.set_mass(mass)
        # check individual atoms
        assert_equal([a.mass for a in g.atoms],
                     mass * numpy.ones(g.numberOfAtoms()),
                     err_msg="failed to set_mass in segment of  H* atoms in resid 12:42 to {0}".format(mass))

    def test_set_segid_ValueError(self):
        assert_raises(ValueError, self.g.set_resid, [1, 2, 3, 4])


class TestAtomGroupVelocities(TestCase):
    """Tests of velocity-related functions in AtomGroup"""

    def setUp(self):
        self.universe = MDAnalysis.Universe(GRO, TRR)
        self.ag = self.universe.selectAtoms("bynum 12:42")

    @dec.slow
    def test_get_velocities(self):
        v = self.ag.get_velocities()
        assert_(numpy.any(numpy.abs(v) > 1e-6), "velocities should be non-zero")

    def test_vel_src(self):
        assert_equal(self.universe.trajectory.ts.data['velocity_source'], 0)

    @dec.slow
    def test_velocities(self):
        ag = self.universe.atoms[42:45]
        ref_v = numpy.array([
            [-3.61757946, -4.9867239, 2.46281552],
            [2.57792854, 3.25411797, -0.75065529],
            [13.91627216, 30.17778587, -12.16669178]])
        v = ag.velocities
        assert_almost_equal(v, ref_v, err_msg="velocities were not read correctly")

    @dec.slow
    def test_set_velocities(self):
        ag = self.ag
        v = ag.get_velocities() - 2.7271
        ag.set_velocities(v)
        assert_almost_equal(ag.get_velocities(), v,
                            err_msg="messages were not set to new value")


class TestAtomGroupTimestep(TestCase):
    """Tests the AtomGroup.ts attribute (partial timestep)"""

    def setUp(self):
        self.universe = MDAnalysis.Universe(TRZ_psf, TRZ)
        self.prec = 6

    def tearDown(self):
        del self.universe
        del self.prec

    def test_partial_timestep(self):
        ag = self.universe.selectAtoms('name Ca')
        idx = ag.indices()

        assert_equal(len(ag.ts._pos), len(ag))

        for ts in self.universe.trajectory[0:20:5]:
            assert_array_almost_equal(ts._pos[idx], ag.ts._pos, self.prec,
                                      err_msg="Partial timestep coordinates wrong")
            assert_array_almost_equal(ts._velocities[idx], ag.ts._velocities, self.prec,
                                      err_msg="Partial timestep coordinates wrong")


def test_empty_AtomGroup():
    """Test that an empty AtomGroup can be constructed (Issue 12)"""
    ag = MDAnalysis.core.AtomGroup.AtomGroup([])
    assert_equal(len(ag), 0)

class _WriteAtoms(TestCase):
    """Set up the standard AdK system in implicit solvent."""
    ext = None  # override to test various output writers
    precision = 3

    def setUp(self):
        self.universe = MDAnalysis.Universe(PSF, DCD)
        suffix = '.' + self.ext
        fd, self.outfile = tempfile.mkstemp(suffix=suffix)
        os.close(fd)

    def tearDown(self):
        try:
            os.unlink(self.outfile)
        except OSError:
            pass
        del self.universe

    def universe_from_tmp(self):
        return MDAnalysis.Universe(self.outfile, convert_units=True)

    def test_write_atoms(self):
        self.universe.atoms.write(self.outfile)
        u2 = self.universe_from_tmp()
        assert_array_almost_equal(self.universe.atoms.coordinates(), u2.atoms.coordinates(), self.precision,
                                  err_msg="atom coordinate mismatch between original and %s file" % self.ext)

    def test_write_selection(self):
        CA = self.universe.selectAtoms('name CA')
        CA.write(self.outfile)
        u2 = self.universe_from_tmp()
        CA2 = u2.selectAtoms('all')  # check EVERYTHING, otherwise we might get false positives!
        assert_equal(len(u2.atoms), len(CA.atoms), "written CA selection does not match original selection")
        assert_almost_equal(CA2.coordinates(), CA.coordinates(), self.precision,
                            err_msg="CA coordinates do not agree with original")

    def test_write_Residue(self):
        G = self.universe.s4AKE.ARG[-2]  # 2nd but last Arg
        G.write(self.outfile)
        u2 = self.universe_from_tmp()
        G2 = u2.selectAtoms('all')  # check EVERYTHING, otherwise we might get false positives!
        assert_equal(len(u2.atoms), len(G.atoms), "written R206 Residue does not match original ResidueGroup")
        assert_almost_equal(G2.coordinates(), G.coordinates(), self.precision,
                            err_msg="Residue R206 coordinates do not agree with original")

    def test_write_ResidueGroup(self):
        G = self.universe.s4AKE.LEU
        G.write(self.outfile)
        u2 = self.universe_from_tmp()
        G2 = u2.selectAtoms('all')  # check EVERYTHING, otherwise we might get false positives!
        assert_equal(len(u2.atoms), len(G.atoms), "written LEU ResidueGroup does not match original ResidueGroup")
        assert_almost_equal(G2.coordinates(), G.coordinates(), self.precision,
                            err_msg="ResidueGroup LEU coordinates do not agree with original")

    def test_write_Segment(self):
        G = self.universe.s4AKE
        G.write(self.outfile)
        u2 = self.universe_from_tmp()
        G2 = u2.selectAtoms('all')  # check EVERYTHING, otherwise we might get false positives!
        assert_equal(len(u2.atoms), len(G.atoms), "written s4AKE segment does not match original segment")
        assert_almost_equal(G2.coordinates(), G.coordinates(), self.precision,
                            err_msg="segment s4AKE coordinates do not agree with original")

    def test_write_Universe(self):
        U = self.universe
        W = MDAnalysis.Writer(self.outfile)
        W.write(U)
        W.close()
        u2 = self.universe_from_tmp()
        assert_equal(len(u2.atoms), len(U.atoms), "written 4AKE universe does not match original universe in size")
        assert_almost_equal(u2.atoms.coordinates(), U.atoms.coordinates(), self.precision,
                            err_msg="written universe 4AKE coordinates do not agree with original")

class TestWritePDB(_WriteAtoms):
    ext = "pdb"
    precision = 3


import MDAnalysis.coordinates


class TestWriteCRD(_WriteAtoms):
    ext = "crd"
    precision = 5


class TestWriteGRO(_WriteAtoms):
    ext = "gro"
    precision = 2

    def test_flag_convert_length(self):
        assert_equal(MDAnalysis.core.flags['convert_lengths'], True,
                     "The flag convert_lengths SHOULD be True by default! "
                     "(If it is not then this might indicate a race condition in the "
                     "testing suite.)")


import MDAnalysis.core.AtomGroup


@attr("issue")
def test_generated_residueselection():
    """Test that a generated residue group always returns a ResidueGroup (Issue 47)"""
    universe = MDAnalysis.Universe(PSF, DCD)
    # only a single Cys in AdK
    cys = universe.s4AKE.CYS
    assert_(isinstance(cys, MDAnalysis.core.AtomGroup.ResidueGroup),
            "Single Cys77 is NOT returned as a ResidueGroup with a single Residue (Issue 47)")

    # multiple Met
    met = universe.s4AKE.MET
    assert_(isinstance(met, MDAnalysis.core.AtomGroup.ResidueGroup),
            "Met selection does not return a ResidueGroup")

    del universe


@attr('issue')
def test_instantselection_termini():
    """Test that instant selections work, even for residues that are also termini (Issue 70)"""
    universe = MDAnalysis.Universe(PSF, DCD)
    assert_equal(universe.residues[20].CA.name, 'CA', "CA of MET21 is not selected correctly")
    del universe


class TestUniverse(TestCase):
    def test_load(self):
        # Universe(top, trj)
        u = MDAnalysis.Universe(PSF, PDB_small)
        assert_equal(len(u.atoms), 3341, "Loading universe failed somehow")

    def test_load_bad_topology(self):
        # tests that Universe builds produce the right error message
        def bad_load():
            return MDAnalysis.Universe(PSF_BAD, DCD)

        assert_raises(ValueError, bad_load)

    @attr('issue')
    def test_load_new(self):
        u = MDAnalysis.Universe(PSF, DCD)
        u.load_new(PDB_small)
        assert_equal(len(u.trajectory), 1, "Failed to load_new(PDB)")

    def test_load_new_strict(self):
        u = MDAnalysis.Universe(PSF, DCD)
        u.load_new(PDB_small, permissive=False)
        assert_equal(len(u.trajectory), 1, "Failed to load_new(PDB, permissive=False)")

    def test_load_new_permissive(self):
        u = MDAnalysis.Universe(PSF, DCD)
        u.load_new(PDB_small, permissive=True)
        assert_equal(len(u.trajectory), 1, "Failed to load_new(PDB, permissive=True)")

    def test_load_new_TypeError(self):
        u = MDAnalysis.Universe(PSF, DCD)

        def bad_load(uni):
            return uni.load_new('filename.notarealextension')

        assert_raises(TypeError, bad_load, u)

    def test_load_structure(self):
        # Universe(struct)
        ref = MDAnalysis.Universe(PSF, PDB_small)
        u = MDAnalysis.Universe(PDB_small)
        assert_equal(len(u.atoms), 3341, "Loading universe failed somehow")
        assert_almost_equal(u.atoms.positions, ref.atoms.positions)

    def test_load_multiple_list(self):
        # Universe(top, [trj, trj, ...])
        ref = MDAnalysis.Universe(PSF, DCD)
        u = MDAnalysis.Universe(PSF, [DCD, DCD])
        assert_equal(len(u.atoms), 3341, "Loading universe failed somehow")
        assert_equal(u.trajectory.numframes, 2 * ref.trajectory.numframes)

    def test_load_multiple_args(self):
        # Universe(top, trj, trj, ...)
        ref = MDAnalysis.Universe(PSF, DCD)
        u = MDAnalysis.Universe(PSF, DCD, DCD)
        assert_equal(len(u.atoms), 3341, "Loading universe failed somehow")
        assert_equal(u.trajectory.numframes, 2 * ref.trajectory.numframes)

    def test_pickle_raises_NotImplementedError(self):
        import cPickle

        u = MDAnalysis.Universe(PSF, DCD)
        assert_raises(NotImplementedError, cPickle.dumps, u, protocol=cPickle.HIGHEST_PROTOCOL)

    def test_set_dimensions(self):
        u = MDAnalysis.Universe(PSF, DCD)
        box = numpy.array([10, 11, 12, 90, 90, 90])
        u.dimensions = numpy.array([10, 11, 12, 90, 90, 90])
        assert_allclose(u.dimensions, box)

class TestPBCFlag(TestCase):
    def setUp(self):
        self.prec = 3
        self.universe = MDAnalysis.Universe(TRZ_psf, TRZ)
        self.ref_noPBC = {
            'COG': numpy.array([4.23789883, 0.62429816, 2.43123484], dtype=float32),
            'COM': numpy.array([4.1673783, 0.70507009, 2.21175832]),
            'ROG': 119.30368949900134, 'Shape': 0.6690026954813445,
            'Asph': 0.5305456387833748,
            'MOI': numpy.array([
                [152117.06620921, 55149.54042136, -26630.46034023],
                [55149.54042136, 72869.64061494, 21998.1778074],
                [-26630.46034023, 21998.1778074, 162388.70002471]]),
            'BBox': numpy.array([[-75.74159241, -144.86634827, -94.47974396], [95.83090973, 115.11561584, 88.09812927]],
                                dtype=float32),
            'BSph': (173.40482, numpy.array([4.23789883, 0.62429816, 2.43123484], dtype=float32)),
            'PAxes': numpy.array([
                [0.46294889, -0.85135849, 0.24671249],
                [0.40611024, 0.45112859, 0.7947059],
                [-0.78787867, -0.26771575, 0.55459488]])
        }
        self.ref_PBC = {
            'COG': numpy.array([26.82960892, 31.5592289, 30.98238945], dtype=float32),
            'COM': numpy.array([26.67781143, 31.2104336, 31.19796289]),
            'ROG': 27.713008969174918, 'Shape': 0.0017390512580463542,
            'Asph': 0.020601215358731016,
            'MOI': numpy.array([
                [7333.79167791, -211.8997285, -721.50785456],
                [-211.8997285, 7059.07470427, -91.32156884],
                [-721.50785456, -91.32156884, 6509.31735029]]),
            'BBox': numpy.array(
                [[1.45964116e-01, 1.85623169e-02, 4.31785583e-02], [5.53314018e+01, 5.54227829e+01, 5.54158211e+01]],
                dtype=float32),
            'BSph': (47.923367, numpy.array([26.82960892, 31.5592289, 30.98238945], dtype=float32)),
            'PAxes': numpy.array([
                [-0.50622389, -0.18364489, -0.84262206],
                [-0.07520116, -0.96394227, 0.25526473],
                [-0.85911708, 0.19258726, 0.4741603]])
        }
        self.ag = self.universe.residues[0:3]

    def tearDown(self):
        MDAnalysis.core.flags['use_pbc'] = False
        del self.universe
        del self.ref_noPBC
        del self.ref_PBC
        del self.ag

    def test_flag(self):
        # Test default setting of flag
        assert_equal(MDAnalysis.core.flags['use_pbc'], False)

    def test_default(self):
        # Test regular behaviour
        assert_almost_equal(self.ag.centerOfGeometry(), self.ref_noPBC['COG'], self.prec)
        assert_almost_equal(self.ag.centerOfMass(), self.ref_noPBC['COM'], self.prec)
        assert_almost_equal(self.ag.radiusOfGyration(), self.ref_noPBC['ROG'], self.prec)
        assert_almost_equal(self.ag.shapeParameter(), self.ref_noPBC['Shape'], self.prec)
        assert_almost_equal(self.ag.asphericity(), self.ref_noPBC['Asph'], self.prec)
        assert_almost_equal(self.ag.momentOfInertia(), self.ref_noPBC['MOI'], self.prec)
        assert_almost_equal(self.ag.bbox(), self.ref_noPBC['BBox'], self.prec)
        assert_almost_equal(self.ag.bsphere()[0], self.ref_noPBC['BSph'][0], self.prec)
        assert_almost_equal(self.ag.bsphere()[1], self.ref_noPBC['BSph'][1], self.prec)
        assert_almost_equal(self.ag.principalAxes(), self.ref_noPBC['PAxes'], self.prec)

    def test_pbcflag(self):
        # Test using ag method flag
        assert_almost_equal(self.ag.centerOfGeometry(pbc=True), self.ref_PBC['COG'], self.prec)
        assert_almost_equal(self.ag.centerOfMass(pbc=True), self.ref_PBC['COM'], self.prec)
        assert_almost_equal(self.ag.radiusOfGyration(pbc=True), self.ref_PBC['ROG'], self.prec)
        assert_almost_equal(self.ag.shapeParameter(pbc=True), self.ref_PBC['Shape'], self.prec)
        assert_almost_equal(self.ag.asphericity(pbc=True), self.ref_PBC['Asph'], self.prec)
        assert_almost_equal(self.ag.momentOfInertia(pbc=True), self.ref_PBC['MOI'], self.prec)
        assert_almost_equal(self.ag.bbox(pbc=True), self.ref_PBC['BBox'], self.prec)
        assert_almost_equal(self.ag.bsphere(pbc=True)[0], self.ref_PBC['BSph'][0], self.prec)
        assert_almost_equal(self.ag.bsphere(pbc=True)[1], self.ref_PBC['BSph'][1], self.prec)
        assert_almost_equal(self.ag.principalAxes(pbc=True), self.ref_PBC['PAxes'], self.prec)

    def test_usepbc_flag(self):
        # Test using the core.flags flag
        MDAnalysis.core.flags['use_pbc'] = True
        assert_almost_equal(self.ag.centerOfGeometry(), self.ref_PBC['COG'], self.prec)
        assert_almost_equal(self.ag.centerOfMass(), self.ref_PBC['COM'], self.prec)
        assert_almost_equal(self.ag.radiusOfGyration(), self.ref_PBC['ROG'], self.prec)
        assert_almost_equal(self.ag.shapeParameter(), self.ref_PBC['Shape'], self.prec)
        assert_almost_equal(self.ag.asphericity(), self.ref_PBC['Asph'], self.prec)
        assert_almost_equal(self.ag.momentOfInertia(), self.ref_PBC['MOI'], self.prec)
        assert_almost_equal(self.ag.bbox(), self.ref_PBC['BBox'], self.prec)
        assert_almost_equal(self.ag.bsphere()[0], self.ref_PBC['BSph'][0], self.prec)
        assert_almost_equal(self.ag.bsphere()[1], self.ref_PBC['BSph'][1], self.prec)
        assert_almost_equal(self.ag.principalAxes(), self.ref_PBC['PAxes'], self.prec)
        MDAnalysis.core.flags['use_pbc'] = False

    def test_override_flag(self):
        # Test using the core.flags flag, then overriding
        MDAnalysis.core.flags['use_pbc'] = True
        assert_almost_equal(self.ag.centerOfGeometry(pbc=False), self.ref_noPBC['COG'], self.prec)
        assert_almost_equal(self.ag.centerOfMass(pbc=False), self.ref_noPBC['COM'], self.prec)
        assert_almost_equal(self.ag.radiusOfGyration(pbc=False), self.ref_noPBC['ROG'], self.prec)
        assert_almost_equal(self.ag.shapeParameter(pbc=False), self.ref_noPBC['Shape'], self.prec)
        assert_almost_equal(self.ag.asphericity(pbc=False), self.ref_noPBC['Asph'], self.prec)
        assert_almost_equal(self.ag.momentOfInertia(pbc=False), self.ref_noPBC['MOI'], self.prec)
        assert_almost_equal(self.ag.bbox(pbc=False), self.ref_noPBC['BBox'], self.prec)
        assert_almost_equal(self.ag.bsphere(pbc=False)[0], self.ref_noPBC['BSph'][0], self.prec)
        assert_almost_equal(self.ag.bsphere(pbc=False)[1], self.ref_noPBC['BSph'][1], self.prec)
        assert_almost_equal(self.ag.principalAxes(pbc=False), self.ref_noPBC['PAxes'], self.prec)
        MDAnalysis.core.flags['use_pbc'] = False


class TestAsUniverse(TestCase):
    def setUp(self):
        self.u = MDAnalysis.Universe(PSF_notop, DCD)

    def tearDown(self):
        del self.u

    def test_empty_TypeError(self):
        assert_raises(TypeError, asUniverse)

    def test_passback(self):
        returnval = asUniverse(self.u)

        assert_equal(returnval is self.u, True)

    def test_makeuni(self):
        returnval = asUniverse(PSF_notop, DCD)

        ## __eq__ method for Universe doesn't exist, make one up here
        assert_equal(set(returnval.atoms), set(self.u.atoms))


class TestFragments(TestCase):
    def setUp(self):
        self.u = MDAnalysis.Universe(PSF, DCD)
        # To create a fragment with only one atom in, remove a bond
        self.u._topology['bonds'].remove((2, 0))

    def tearDown(self):
        del self.u

    def test_nobondsfail(self):
        u2 = MDAnalysis.Universe(XYZ_mini)

        def query_frag(u):
            return u.fragments

        assert_raises(NoDataError, query_frag, u2)

    def test_make_fragments(self):
        # Test that the Universe method for making fragments works
        # This checks that the correct number of fragments are made
        frag = self.u.fragments

        assert_equal(len(frag), 2)  # normally has one but I removed a bond

    def test_single_fragment(self):
        # I removed the bond from this atom so it's in a fragment on its own
        assert_equal(len(self.u.atoms[2].fragment), 1)

    def test_fragment_coverage(self):
        # Test that fragments contain all the atoms in Universe
        frags = self.u.fragments

        natoms = sum([len(f) for f in frags])

        assert_equal(natoms, len(self.u.atoms))

    def test_make_fragDict(self):
        # Test that the fragDict contains all Atoms
        fd = self.u._fragmentDict

        for a in self.u.atoms:
            assert_equal(a in fd, True)

    def test_atom_lookup(self):
        # check that looking up a fragment from an Atom when "cold" works
        assert_equal(self.u.atoms[0].fragment is self.u.atoms[4].fragment, True)

    def test_atomgroup_lookup(self):
        # check that atomgroups return the fragments ok
        ag = self.u.atoms[100:200]
        assert_equal(len(ag.fragments), 1)


class TestUniverseCache(TestCase):
    def setUp(self):
        self.u = MDAnalysis.Universe()  # not using atoms so just blank universe
        self.fill = [1, 2, 3]

    def tearDown(self):
        del self.u
        del self.fill

    def test_add_to_cache(self):
        # add an item to cache and see if it sticks
        cache = 'aa'
        self.u._fill_cache(cache, self.fill)

        assert_equal('aa' in self.u._cache, True)
        assert_equal(self.u._cache[cache], self.fill)

    def test_remove_single(self):
        # remove a single item from cache
        cache = 'bb'

        self.u._fill_cache(cache, self.fill)

        assert_equal(cache in self.u._cache, True)

        self.u._clear_caches(cache)

        assert_equal(cache in self.u._cache, False)

    def test_remove_list(self):
        # remove a few things from cache
        caches = ['cc', 'dd']
        for c in caches:
            self.u._fill_cache(c, self.fill)

        for c in caches:
            assert_equal(c in self.u._cache, True)

        self.u._clear_caches(*caches)

        for c in caches:
            assert_equal(c in self.u._cache, False)

    def test_clear_all(self):
        # remove everything from cache
        caches = ['ee', 'ff', 'gg']
        for c in caches:
            self.u._fill_cache(c, self.fill)

        self.u._clear_caches()

        assert_equal(self.u._cache, dict())


class TestUnorderedResidues(TestCase):
    """
    This pdb file has resids that are non sequential

    This (previously) led to too many residues being found.
    """

    def setUp(self):
        self.u = MDAnalysis.Universe(unordered_res)

    def tearDown(self):
        del self.u

    @attr("issue")
    def test_build_residues(self):
        assert_equal(len(self.u.residues), 35)

class TestCustomReaders(TestCase):
    """
    Can pass a reader as kwarg on Universe creation
    """
    def test_custom_reader(self):
        # check that reader passing works
        u = MDAnalysis.Universe(TRZ_psf, TRZ, format=MDAnalysis.coordinates.TRZ.TRZReader)
        assert_equal(len(u.atoms), 8184)

    def test_custom_reader_singleframe(self):
        T = MDAnalysis.topology.GROParser.GROParser
        R = MDAnalysis.coordinates.GRO.GROReader
        u = MDAnalysis.Universe(two_water_gro, two_water_gro,
                                topology_format=T, format=R)
        assert_equal(len(u.atoms), 6)

    def test_custom_reader_singleframe_2(self):
        # Same as before, but only one argument to Universe
        T = MDAnalysis.topology.GROParser.GROParser
        R = MDAnalysis.coordinates.GRO.GROReader
        u = MDAnalysis.Universe(two_water_gro,
                                topology_format=T, format=R)
        assert_equal(len(u.atoms), 6)

    def test_custom_parser(self):
        # topology reader passing works
        u = MDAnalysis.Universe(TRZ_psf, TRZ, topology_format=MDAnalysis.topology.PSFParser.PSFParser)
        assert_equal(len(u.atoms), 8184)

    def test_custom_both(self):
        # use custom for both
        u = MDAnalysis.Universe(TRZ_psf, TRZ, format=MDAnalysis.coordinates.TRZ.TRZReader,
                                topology_format=MDAnalysis.topology.PSFParser.PSFParser)
        assert_equal(len(u.atoms), 8184)

class TestWrap(TestCase):
    def setUp(self):
        self.u = MDAnalysis.Universe(TRZ_psf, TRZ)
        self.ag = self.u.atoms[:100]

    def tearDown(self):
        del self.u
        del self.ag

    def test_wrap_comp_fail(self):
        assert_raises(ValueError, self.ag.wrap, compound='strawberries')

    def test_wrap_cent_fail(self):
        assert_raises(ValueError, self.ag.wrap, compound='residues', center='avacado')

    def test_wrap_box_fail(self):
        assert_raises(ValueError, self.ag.wrap, box=numpy.array([0, 1]))

    def _in_box(self, coords):
        """Check that a set of coordinates are 0.0 <= r <= box"""
        box = self.u.dimensions[:3]

        return (coords >= 0.0).all() and (coords <= box).all()

    def test_wrap_atoms(self):
        ag = self.u.atoms[100:200]
        ag.wrap(compound='atoms')

        assert_equal(self._in_box(ag.positions), True)

    def test_wrap_group(self):
        ag = self.u.atoms[:100]
        ag.wrap(compound='group')

        cen = ag.centerOfMass()

        assert_equal(self._in_box(cen), True)

    def test_wrap_residues(self):
        ag = self.u.atoms[300:400]
        ag.wrap(compound='residues')

        cen = numpy.vstack([r.centerOfMass() for r in ag.residues])

        assert_equal(self._in_box(cen), True)

    def test_wrap_segments(self):
        ag = self.u.atoms[1000:1200]
        ag.wrap(compound='segments')

        cen = numpy.vstack([s.centerOfMass() for s in ag.segments])

        assert_equal(self._in_box(cen), True)

    def test_wrap_fragments(self):
        ag = self.u.atoms[:250]
        ag.wrap(compound='fragments')

        cen = numpy.vstack([f.centerOfMass() for f in ag.fragments])

        assert_equal(self._in_box(cen), True)


class TestGuessBonds(TestCase):
    """Test the AtomGroup methed guess_bonds

    This needs to be done both from Universe creation (via kwarg) and AtomGroup

    It needs to:
     - work if all atoms are in vdwradii table
     - fail properly if not
     - work again if vdwradii are passed.
    """
    def setUp(self):
        self.vdw = {'A':1.05, 'B':0.4}

    def tearDown(self):
        del self.vdw

    def _check_universe(self, u):
        """Verify that the Universe is created correctly"""
        assert_equal(len(u.bonds), 4)
        assert_equal(len(u.angles), 2)
        assert_equal(len(u.torsions), 0)
        assert_equal(len(u.atoms[0].bonds), 2)
        assert_equal(len(u.atoms[1].bonds), 1)
        assert_equal(len(u.atoms[2].bonds), 1)
        assert_equal(len(u.atoms[3].bonds), 2)
        assert_equal(len(u.atoms[4].bonds), 1)
        assert_equal(len(u.atoms[5].bonds), 1)

    def test_universe_guess_bonds(self):
        """Test that making a Universe with guess_bonds works"""
        u = MDAnalysis.Universe(two_water_gro, guess_bonds=True)
        self._check_universe(u)

    def test_universe_guess_bonds_no_vdwradii(self):
        """Make a Universe that has atoms with unknown vdwradii."""
        assert_raises(ValueError, MDAnalysis.Universe, two_water_gro_nonames, guess_bonds=True)

    def test_universe_guess_bonds_with_vdwradii(self):
        """Unknown atom types, but with vdw radii here to save the day"""
        u = MDAnalysis.Universe(two_water_gro_nonames, guess_bonds=True,
                                vdwradii=self.vdw)
        self._check_universe(u)

    def test_universe_guess_bonds_off(self):
        u = MDAnalysis.Universe(two_water_gro_nonames, guess_bonds=False)

        assert_equal(len(u.bonds), 0)
        assert_equal(len(u.angles), 0)
        assert_equal(len(u.torsions), 0)

    def _check_atomgroup(self, ag, u):
        """Verify that the AtomGroup made bonds correctly,
        and that the Universe got all this info
        """
        assert_equal(len(ag.bonds), 2)
        assert_equal(len(ag.angles), 1)
        assert_equal(len(ag.torsions), 0)
        assert_equal(len(u.bonds), 2)
        assert_equal(len(u.angles), 1)
        assert_equal(len(u.torsions), 0)
        assert_equal(len(u.atoms[0].bonds), 2)
        assert_equal(len(u.atoms[1].bonds), 1)
        assert_equal(len(u.atoms[2].bonds), 1)
        assert_equal(len(u.atoms[3].bonds), 0)
        assert_equal(len(u.atoms[4].bonds), 0)
        assert_equal(len(u.atoms[5].bonds), 0)

    def test_atomgroup_guess_bonds(self):
        """Test an atomgroup doing guess bonds"""
        u = MDAnalysis.Universe(two_water_gro)

        ag = u.atoms[:3]
        ag.guess_bonds()
        self._check_atomgroup(ag, u)

    def test_atomgroup_guess_bonds_no_vdwradii(self):
        u = MDAnalysis.Universe(two_water_gro_nonames)

        ag = u.atoms[:3]
        assert_raises(ValueError, ag.guess_bonds)

    def test_atomgroup_guess_bonds_with_vdwradii(self):
        u = MDAnalysis.Universe(two_water_gro_nonames)

        ag = u.atoms[:3]
        ag.guess_bonds(vdwradii=self.vdw)
        self._check_atomgroup(ag, u)


class TestAtomGroupSettingGetting(object):
    """Test working with the properties of Atoms via AtomGroups

    list of properties:
    - name x
    - altLoc x - can't play via AG
    - type x 
    - mass x 
    - charge x
    - radius x 
    - bfactor x - ugly hack for getting because it's a property
    - serial x - can't play via AG

    Residue/Segment related ones:
    - resname
    - resid
    - resnum
    - residue?
    - segid?
    - segment?

    Check that:
    - getting properties from AG matches the Atom values
    - setting properties from AG changes the Atom
    - setting the property on Atom changes AG
    """
    def get_new(self, att_type):
        """Return enough values to change the small g"""
        if att_type == 'string':
            return ['A', 'B', 'C', 'D', 'E', 'F']
        elif att_type == 'float':
            return [0.001, 0.002, 0.003, 0.005, 0.012, 0.025]
        elif att_type == 'int':
            return [4, 6, 8, 1, 5, 4]

    def _check_ag_matches_atom(self, att, ag, ag_meth):
        """Checking Atomgroup matches Atoms"""
        # Check that accessing via AtomGroup is identical to doing
        # a list comprehension over AG
        ref = ag_meth()
        other = [getattr(atom, att) for atom in ag]

        assert_equal(ref, other,
                     err_msg="AtomGroup doesn't match Atoms for property: {0}".format(att))

    def _change_atom_check_ag(self, att, vals, ag, ag_meth):
        """Changing Atom, checking AtomGroup"""
        # Set attributes via Atoms
        for atom, val in zip(ag, vals):
            setattr(atom, att, val)
        ag._clear_caches()
        # Check that AtomGroup returns new values
        assert_equal(vals, ag_meth(),
                     err_msg="Change to Atoms not reflected in AtomGroup for property: {0}".format(att))

    def _change_ag_check_atoms(self, att, vals, ag, ag_meth):
        """Changing AtomGroup, checking Atoms"""
        ag_meth(vals)

        for atom, val in zip(ag, vals):
            assert_equal(getattr(atom, att), val,
                         err_msg="Change to AtomGroup not reflected in Atoms for propert: {0}".format(att))

    def test_attributes(self):
        u = MDAnalysis.Universe(PSF, DCD)
        master = u.atoms
        idx = [0, 1, 4, 7, 11, 14]
        ag = master[idx]

        def get_bfac():
            return ag.bfactors

        for att, att_type, ag_meth, ag_set in (
                ('name', 'string', ag.names, ag.set_name),
                ('type', 'string', ag.types, ag.set_type),
                ('altLoc', 'string', None, None),  # can't access via AG
                ('serial', 'int', None, None),  # can't access via AG
                ('charge', 'float', ag.charges, ag.set_charge),
                ('mass', 'float', ag.masses, ag.set_mass),
                ('radius', 'float', ag.radii, ag.set_radius),
                ('bfactor', 'float', get_bfac, ag.set_bfactor)
        ):
            vals = self.get_new(att_type)
            if not ag_meth is None:
                yield self._check_ag_matches_atom, att, ag, ag_meth
            if not ag_meth is None:
                yield self._change_atom_check_ag, att, vals, ag, ag_meth
            if not ag_set is None:
                yield self._change_ag_check_atoms, att, vals, ag, ag_set
