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
import MDAnalysis.core.Selection
from MDAnalysis.tests.datafiles import PSF, DCD, PRMpbc, TRJpbc_bz2, PSF_NAMD, PDB_NAMD, GRO, NUCL, TPR, XTC

from numpy.testing import *
from numpy import array, float32, arange
from nose.plugins.attrib import attr

from MDAnalysisTests.plugins.knownfailure import knownfailure

class TestSelectionsCHARMM(TestCase):
    def setUp(self):
        """Set up the standard AdK system in implicit solvent."""
        self.universe = MDAnalysis.Universe(PSF, DCD)

    def tearDown(self):
        self.universe.trajectory.close()
        del self.universe

    def test_segid(self):
        sel = self.universe.selectAtoms('segid 4AKE')
        assert_equal(sel.numberOfAtoms(), 3341, "failed to select segment 4AKE")
        assert_equal(sel._atoms, self.universe.s4AKE._atoms,
                     "selected segment 4AKE is not the same as auto-generated segment s4AKE")

    def test_protein(self):
        sel = self.universe.selectAtoms('protein')
        assert_equal(sel.numberOfAtoms(), 3341, "failed to select protein")
        assert_equal(sel._atoms, self.universe.s4AKE._atoms,
                     "selected protein is not the same as auto-generated protein segment s4AKE")

    def test_backbone(self):
        sel = self.universe.selectAtoms('backbone')
        assert_equal(sel.numberOfAtoms(), 855)

    def test_resid_single(self):
        sel = self.universe.selectAtoms('resid 100')
        assert_equal(sel.numberOfAtoms(), 7)
        assert_equal(sel.resnames(), ['GLY'])

    def test_resid_range(self):
        sel = self.universe.selectAtoms('resid 100:105')
        assert_equal(sel.numberOfAtoms(), 89)
        assert_equal(sel.resnames(), ['GLY', 'ILE', 'ASN', 'VAL', 'ASP', 'TYR'])

    def test_selgroup(self):
        sel = self.universe.selectAtoms('not resid 100')
        sel2 = self.universe.selectAtoms('not group notr100', notr100=sel)
        assert_equal(sel2.numberOfAtoms(), 7)
        assert_equal(sel2.resnames(), ['GLY'])

    def test_fullselgroup(self):
        sel1 = self.universe.selectAtoms('resid 101')
        sel2 = self.universe.selectAtoms('resid 100')
        sel3 = sel1.selectAtoms('fullgroup r100', r100=sel2)
        assert_equal(sel2.numberOfAtoms(), 7)
        assert_equal(sel2.resnames(), ['GLY'])

    # resnum selections are boring here because we haven't really a mechanism yet
    # to assign the canonical PDB resnums
    def test_resnum_single(self):
        sel = self.universe.selectAtoms('resnum 100')
        assert_equal(sel.numberOfAtoms(), 7)
        assert_equal(sel.resids(), [100])
        assert_equal(sel.resnames(), ['GLY'])

    def test_resnum_range(self):
        sel = self.universe.selectAtoms('resnum 100:105')
        assert_equal(sel.numberOfAtoms(), 89)
        assert_equal(sel.resids(), range(100, 106))
        assert_equal(sel.resnames(), ['GLY', 'ILE', 'ASN', 'VAL', 'ASP', 'TYR'])

    def test_resname(self):
        sel = self.universe.selectAtoms('resname LEU')
        assert_equal(sel.numberOfAtoms(), 304, "Failed to find all 'resname LEU' atoms.")
        assert_equal(sel.numberOfResidues(), 16, "Failed to find all 'resname LEU' residues.")
        assert_equal(sel._atoms, self.universe.s4AKE.LEU._atoms,
                     "selected 'resname LEU' atoms are not the same as auto-generated s4AKE.LEU")

    def test_name(self):
        sel = self.universe.selectAtoms('name CA')
        assert_equal(sel.numberOfAtoms(), 214)

    def test_atom(self):
        sel = self.universe.selectAtoms('atom 4AKE 100 CA')
        assert_equal(len(sel), 1)
        assert_equal(sel.resnames(), ['GLY'])
        assert_array_almost_equal(sel.coordinates(),
                                  array([[20.38685226, -3.44224262, -5.92158318]], dtype=float32))

    def test_type(self):
        sel = self.universe.selectAtoms("type 1")
        assert_equal(len(sel), 253)

    def test_and(self):
        sel = self.universe.selectAtoms('resname GLY and resid 100')
        assert_equal(len(sel), 7)

    def test_or(self):
        sel = self.universe.selectAtoms('resname LYS or resname ARG')
        assert_equal(sel.numberOfResidues(), 31)

    def test_not(self):
        sel = self.universe.selectAtoms('not backbone')
        assert_equal(len(sel), 2486)

    def test_around(self):
        sel = self.universe.selectAtoms('around 4.0 bynum 1943')
        assert_equal(len(sel), 32)

    def test_sphlayer(self):
        sel = self.universe.selectAtoms('sphlayer 4.0 6.0 bynum 1281')
        assert_equal(len(sel), 66)

    def test_sphzone(self):
        sel = self.universe.selectAtoms('sphzone 6.0 bynum 1281')
        assert_equal(len(sel), 86)

    def test_cylayer(self):
        sel = self.universe.selectAtoms('cylayer 4.0 6.0 10 -10 bynum 1281')
        assert_equal(len(sel), 88)

    def test_cyzone(self):
        sel = self.universe.selectAtoms('cyzone 6.0 10 -10 bynum 1281')
        assert_equal(len(sel), 166)

    def test_prop(self):
        sel = self.universe.selectAtoms('prop y <= 16')
        sel2 = self.universe.selectAtoms('prop abs z < 8')
        assert_equal(len(sel), 3194)
        assert_equal(len(sel2), 2001)

    def test_bynum(self):
        "Tests the bynum selection, also from AtomGroup instances (Issue 275)"
        sel = self.universe.selectAtoms('bynum 5')
        assert_equal(sel[0].number, 4)
        sel = self.universe.selectAtoms('bynum 1:10')
        assert_equal(len(sel), 10)
        assert_equal(sel[0].number, 0)
        assert_equal(sel[-1].number, 9)
        subsel = sel.selectAtoms('bynum 5')
        assert_equal(subsel[0].number, 4)
        subsel = sel.selectAtoms('bynum 2:5')
        assert_equal(len(subsel), 4)
        assert_equal(subsel[0].number, 1)
        assert_equal(subsel[-1].number, 4)

    # TODO:
    # add more test cases for byres, bynum, point
    # and also for selection keywords such as 'nucleic'

    def test_same_resname(self):
        """Test the 'same ... as' construct (Issue 217)"""
        sel = self.universe.selectAtoms("same resname as resid 10 or resid 11")
        assert_equal(len(sel), 331, "Found a wrong number of atoms with same resname as resids 10 or 11")
        target_resids = array([ 7, 8, 10, 11, 12, 14, 17, 25, 32, 37, 38, 42, 46,
                               49, 55, 56, 66, 73, 80, 85, 93, 95, 99, 100, 122, 127,
                              130, 144, 150, 176, 180, 186, 188, 189, 194, 198, 203, 207, 214])
        assert_array_equal(sel.resids(), target_resids, "Found wrong residues with same resname as resids 10 or 11")

    def test_same_segment(self):
        """Test the 'same ... as' construct (Issue 217)"""
        self.universe.residues[:100].set_segid("A")  # make up some segments
        self.universe.residues[100:150].set_segid("B")
        self.universe.residues[150:].set_segid("C")

        target_resids = arange(100)+1 
        sel = self.universe.selectAtoms("same segment as resid 10")
        assert_equal(len(sel), 1520, "Found a wrong number of atoms in the same segment of resid 10")
        assert_array_equal(sel.resids(), target_resids, "Found wrong residues in the same segment of resid 10")

        target_resids = arange(100,150)+1 
        sel = self.universe.selectAtoms("same segment as resid 110")
        assert_equal(len(sel), 797, "Found a wrong number of atoms in the same segment of resid 110")
        assert_array_equal(sel.resids(), target_resids, "Found wrong residues in the same segment of resid 110")

        target_resids = arange(150,self.universe.atoms.numberOfResidues())+1
        sel = self.universe.selectAtoms("same segment as resid 160")
        assert_equal(len(sel), 1024, "Found a wrong number of atoms in the same segment of resid 160")
        assert_array_equal(sel.resids(), target_resids, "Found wrong residues in the same segment of resid 160")

        #cleanup
        self.universe.residues.set_segid("4AKE")



    def test_empty_selection(self):
        """Test that empty selection can be processed (see Issue 12)"""
        assert_equal(len(self.universe.selectAtoms('resname TRP')), 0)  # no Trp in AdK

    def test_parenthesized_expression(self):
        sel = self.universe.selectAtoms('( name CA or name CB ) and resname LEU')
        assert_equal(len(sel), 32)

    def test_no_space_around_parentheses(self):
        """Test that no space is needed around parentheses (Issue 43)."""
        # note: will currently be ERROR because it throws a ParseError
        sel = self.universe.selectAtoms('(name CA or name CB) and resname LEU')
        assert_equal(len(sel), 32)

    # TODO:
    # test for checking ordering and multiple comma-separated selections
    def test_concatenated_selection(self):
        E151 = self.universe.s4AKE.r151
        # note that this is not quite phi... HN should be C of prec. residue
        phi151 = E151.selectAtoms('name HN', 'name N', 'name CA', 'name CB')
        assert_equal(len(phi151), 4)
        assert_equal(phi151[0].name, 'HN', "wrong ordering in selection, should be HN-N-CA-CB")


class TestSelectionsAMBER(TestCase):
    def setUp(self):
        """Set up AMBER system"""
        self.universe = MDAnalysis.Universe(PRMpbc, TRJpbc_bz2)

    def tearDown(self):
        self.universe.trajectory.close()
        del self.universe

    def test_protein(self):
        sel = self.universe.selectAtoms('protein')
        assert_equal(sel.numberOfAtoms(), 22, "failed to select protein")

    def test_backbone(self):
        sel = self.universe.selectAtoms('backbone')
        assert_equal(sel.numberOfAtoms(), 7)

    def test_resid_single(self):
        sel = self.universe.selectAtoms('resid 3')
        assert_equal(sel.numberOfAtoms(), 6)
        assert_equal(sel.resnames(), ['NME'])

    def test_type(self):
        sel = self.universe.selectAtoms('type 1')
        assert_equal(len(sel), 6)
        assert_equal(sel.names(), ['HH31', 'HH32', 'HH33', 'HB1', 'HB2', 'HB3'])


class TestSelectionsNAMD(TestCase):
    def setUp(self):
        """Set up NAMD system"""
        self.universe = MDAnalysis.Universe(PSF_NAMD, PDB_NAMD)

    def tearDown(self):
        self.universe.trajectory.close()
        del self.universe

    def test_protein(self):
        sel = self.universe.selectAtoms('protein or resname HAO or resname ORT')  # must include non-standard residues
        assert_equal(sel.numberOfAtoms(), self.universe.atoms.numberOfAtoms(), "failed to select peptide")
        assert_equal(sel.numberOfResidues(), 6, "failed to select all peptide residues")

    def test_resid_single(self):
        sel = self.universe.selectAtoms('resid 12')
        assert_equal(sel.numberOfAtoms(), 26)
        assert_equal(sel.resnames(), ['HAO'])

    def test_type(self):
        sel = self.universe.selectAtoms('type H')
        assert_equal(len(sel), 5)
        assert_array_equal(sel.names(), ['HN', 'HN', 'HN', 'HH', 'HN'])  # note 4th HH


class TestSelectionsGRO(TestCase):
    def setUp(self):
        """Set up GRO system (implicit types, charges, masses, ...)"""
        self.universe = MDAnalysis.Universe(GRO)

    @dec.slow
    def test_protein(self):
        sel = self.universe.selectAtoms('protein')
        assert_equal(sel.numberOfAtoms(), 3341, "failed to select protein")

    @dec.slow
    def test_backbone(self):
        sel = self.universe.selectAtoms('backbone')
        assert_equal(sel.numberOfAtoms(), 855)

    @dec.slow
    def test_type(self):
        sel = self.universe.selectAtoms('type H')
        assert_equal(len(sel), 23853)
        sel = self.universe.selectAtoms('type S')
        assert_equal(len(sel), 7)
        assert_equal(sel.resnames(), self.universe.selectAtoms("resname CYS or resname MET").resnames())

    @dec.slow
    def test_resid_single(self):
        sel = self.universe.selectAtoms('resid 100')
        assert_equal(sel.numberOfAtoms(), 7)
        assert_equal(sel.resnames(), ['GLY'])

    @dec.slow
    def test_atom(self):
        sel = self.universe.selectAtoms('atom SYSTEM 100 CA')
        assert_equal(len(sel), 1)
        assert_equal(sel.resnames(), ['GLY'])

    @dec.slow
    def test_same_coordinate(self):
        """Test the 'same ... as' construct (Issue 217)"""
        # This test comes here because it's hard to get same _x with full precision formats.
        #  The 'same' construct uses numpy.in1d to compare floats. It might be sensitive to
        #  precision issues, but I am expecting .gro coordinates with the same values to
        #  be converted to the exact same floats, at least in the same machine.
        sel = self.universe.selectAtoms("same x as bynum 1 or bynum 10")
        assert_equal(len(sel), 12, "Found a wrong number of atoms with same x as ids 1 or 10")
        target_ids = array([ 0, 8, 9, 224, 643, 3515, 11210, 14121, 18430, 25418, 35811, 43618])
        assert_array_equal(sel.indices(), target_ids, "Found wrong atoms with same x as ids 1 or 10")

    def test_cylayer(self):
        """Test cylinder layer selections from AtomGroups, and with tricilinic periodicity (Issue 274)"""
        atgp = self.universe.selectAtoms('name OW')
        sel = atgp.selectAtoms('cylayer 10 20 20 -20 bynum 3554')
        assert_equal(len(sel), 1155)

    def test_cyzone(self):
        """Test cylinder zone selections from AtomGroups, and with tricilinic periodicity (Issue 274)"""
        atgp = self.universe.selectAtoms('name OW')
        sel = atgp.selectAtoms('cyzone 20 20 -20 bynum 3554')
        assert_equal(len(sel), 1556)


class TestSelectionsXTC(TestCase):
    def setUp(self):
        self.universe = MDAnalysis.Universe(TPR,XTC)

    # Issue #352
    # Fails because bonds are constraints, not harmonic bonds
    # so no "bonds" are detected, so no fragments can be made
    @knownfailure()
    def test_same_fragment(self):
        """Test the 'same ... as' construct (Issue 217)"""
        # This test comes here because it's a system with solvent, and thus multiple fragments.
        try:
            sel = self.universe.selectAtoms("same fragment as bynum 1")
            assert_equal(len(sel), 3341, "Found a wrong number of atoms on the same fragment as id 1")
            assert_equal(sel._atoms, self.universe.atoms[0].fragment._atoms, "Found a different set of atoms when using the 'same fragment as' construct vs. the .fragment prperty")
        except MDAnalysis.NoDataError:
            assert_equal(True, False)

class TestSelectionsNucleicAcids(TestCase):
    def setUp(self):
        self.universe = MDAnalysis.Universe(NUCL)

    def test_nucleic(self):
        rna = self.universe.selectAtoms("nucleic")
        assert_equal(rna.numberOfAtoms(), 739)
        assert_equal(rna.numberOfResidues(), 23)

    def test_nucleicbackbone(self):
        rna = self.universe.selectAtoms("nucleicbackbone")
        assert_equal(rna.numberOfResidues(), 23)
        assert_equal(rna.numberOfAtoms(), rna.numberOfResidues() * 5 - 1)
        # -1 because this is a single strand of RNA and on P is missing at the 5' end

    # todo: need checks for other selection resnames such as DT DA DG DC DU 

    def test_nucleicbase(self):
        rna = self.universe.selectAtoms("nucleicbase")
        assert_equal(rna.numberOfResidues(), 23)
        assert_equal(rna.numberOfAtoms(), 214)

    def test_nucleicsugar(self):
        rna = self.universe.selectAtoms("nucleicsugar")
        assert_equal(rna.numberOfResidues(), 23)
        assert_equal(rna.numberOfAtoms(), rna.numberOfResidues() * 5)
