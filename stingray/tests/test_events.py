import warnings
import numpy as np
import os
import pytest
from astropy.time import Time

from ..events import EventList
from ..lightcurve import Lightcurve

curdir = os.path.abspath(os.path.dirname(__file__))
datadir = os.path.join(curdir, 'data')

_H5PY_INSTALLED = True
_HAS_YAML = True
_HAS_TIMESERIES = True

try:
    import h5py
except ImportError:
    _H5PY_INSTALLED = False

try:
    import astropy.timeseries
    from astropy.timeseries import TimeSeries
except ImportError:
    _HAS_TIMESERIES = False

try:
    import yaml
except ImportError:
    _HAS_YAML = False

class TestEvents(object):

    @classmethod
    def setup_class(self):
        self.time = [0.5, 1.5, 2.5, 3.5]
        self.counts = [3000, 2000, 2200, 3600]
        self.counts_flat = [3000, 3000, 3000, 3000]
        self.spectrum = [[1, 2, 3, 4, 5, 6],
                         [1000, 2040, 1000, 3000, 4020, 2070]]
        self.gti = np.asarray([[0, 4]])

    def test_warn_wrong_keywords(self):
        with pytest.warns(UserWarning) as record:
            _ = EventList(self.time, self.counts, gti=self.gti, bubu='settete')
        assert np.any(["Unrecognized keywords:" in r.message.args[0]
                       for r in record])

    def test_initiate_from_ndarray(self):
        times = np.sort(
            np.random.uniform(1e8, 1e8 + 1000, 101).astype(np.longdouble))
        ev = EventList(times, mjdref=54600)
        assert np.allclose(ev.time, times, atol=1e-15)
        assert np.allclose(ev.mjdref, 54600)

    def test_initiate_from_astropy_time(self):
        times = np.sort(
            np.random.uniform(1e8, 1e8 + 1000, 101).astype(np.longdouble))
        mjdref = 54600
        mjds = Time(mjdref + times / 86400, format='mjd')
        ev = EventList(mjds, mjdref=mjdref)
        assert np.allclose(ev.time, times, atol=1e-15)
        assert np.allclose(ev.mjdref, mjdref)

    def test_create_high_precision_object(self):
        times = np.sort(
            np.random.uniform(1e8, 1e8 + 1000, 101).astype(np.longdouble))
        ev = EventList(times, high_precision=True)
        assert np.allclose(ev.time, times, atol=1e-15)

    def test_inequal_length(self):
        """Check that exception is raised in case of
        disparity in length of 'time' and 'energy'
        """
        with pytest.raises(ValueError):
            EventList(time=[1, 2, 3], energy=[10, 12])

    def test_to_lc(self):
        """Create a light curve from event list."""
        ev = EventList(self.time, gti=self.gti)
        lc = ev.to_lc(1)
        assert np.allclose(lc.time, [0.5, 1.5, 2.5, 3.5])
        assert (lc.gti == self.gti).all()

    def test_from_lc(self):
        """Load event list from lightcurve"""
        lc = Lightcurve(time=[0.5, 1.5, 2.5], counts=[2, 1, 2])
        ev = EventList.from_lc(lc)

        assert (ev.time == np.array([0.5, 0.5, 1.5, 2.5, 2.5])).all()

    def test_simulate_times_warns_bin_time(self):
        """Simulate photon arrival times for an event list
        from light curve.
        """
        lc = Lightcurve(self.time, self.counts_flat, gti=self.gti)
        ev = EventList()
        with pytest.warns(DeprecationWarning) as record:
            ev.simulate_times(lc, bin_time=lc.dt)
        assert np.any(["Bin time will be ignored"
                       in r.message.args[0] for r in record])
        lc_sim = ev.to_lc(dt=lc.dt, tstart=lc.tstart, tseg=lc.tseg)
        assert np.all((lc - lc_sim).counts < 3 * np.sqrt(lc.counts))

    def test_simulate_times_with_spline(self):
        """Simulate photon arrival times, with use_spline option
        enabled.
        """
        lc = Lightcurve(self.time, self.counts_flat, gti=self.gti)
        ev = EventList()
        ev.simulate_times(lc, use_spline=True)
        lc_sim = ev.to_lc(dt=lc.dt, tstart=lc.tstart, tseg=lc.tseg)
        assert np.all((lc - lc_sim).counts < 3 * np.sqrt(lc.counts))

    def test_simulate_energies(self):
        """Assign photon energies to an event list.
        """
        ev = EventList(ncounts=100)
        ev.simulate_energies(self.spectrum)

    def test_simulate_energies_with_1d_spectrum(self):
        """Test that simulate_energies() method raises index
        error exception is spectrum is 1-d.
        """
        ev = EventList(ncounts=100)
        with pytest.raises(IndexError):
            ev.simulate_energies(self.spectrum[0])

    def test_simulate_energies_with_wrong_spectrum_type(self):
        """Test that simulate_energies() method raises type error
        exception when wrong sepctrum type is supplied.
        """
        ev = EventList(ncounts=100)
        with pytest.raises(TypeError):
            ev.simulate_energies(1)

    def test_simulate_energies_with_counts_not_set(self):
        ev = EventList()
        with warnings.catch_warnings(record=True):
            ev.simulate_energies(self.spectrum)

    def test_compare_energy(self):
        """Compare the simulated energy distribution to actual distribution.
        """
        fluxes = np.array(self.spectrum[1])
        ev = EventList(ncounts=1000)
        ev.simulate_energies(self.spectrum)
        energy = [int(p) for p in ev.energy]

        # Histogram energy to get shape approximation
        gen_energy = ((np.array(energy) - 1) / 1).astype(int)
        lc = np.bincount(energy)

        # Remove first entry as it contains occurences of '0' element
        lc = lc[1:len(lc)]

        # Calculate probabilities and compare
        lc_prob = (lc/float(sum(lc)))
        fluxes_prob = fluxes/float(sum(fluxes))

        assert np.all(np.abs(lc_prob - fluxes_prob) < 3 * np.sqrt(fluxes_prob))

    def test_join_without_times_simulated(self):
        """Test if exception is raised when join method is
        called before first simulating times.
        """
        ev = EventList()
        ev_other = EventList()

        assert ev.join(ev_other).time is None

    def test_join_empty_lists(self):
        """Test if an empty event list can be concatenated
        with a non-empty event list.
        """
        ev = EventList(time=[1, 2, 3])
        ev_other = EventList()
        with warnings.catch_warnings(record=True):
            ev_new = ev.join(ev_other)
        assert np.allclose(ev_new.time, [1, 2, 3])

        ev = EventList()
        ev_other = EventList(time=[1, 2, 3])
        with warnings.catch_warnings(record=True):
            ev_new = ev.join(ev_other)
        assert np.allclose(ev_new.time, [1, 2, 3])

        ev = EventList()
        ev_other = EventList()
        with warnings.catch_warnings(record=True):
            ev_new = ev.join(ev_other)
        assert ev_new.time == None
        assert ev_new.gti == None
        assert ev_new.pi == None
        assert ev_new.energy == None

        ev = EventList(time=[1, 2, 3])
        ev_other = EventList([])
        with warnings.catch_warnings(record=True):
            ev_new = ev.join(ev_other)
        assert np.allclose(ev_new.time, [1, 2, 3])
        ev = EventList([])
        ev_other = EventList(time=[1, 2, 3])
        with warnings.catch_warnings(record=True):
            ev_new = ev.join(ev_other)
        assert np.allclose(ev_new.time, [1, 2, 3])

    def test_join_different_dt(self):
        ev = EventList(time=[10, 20, 30], dt = 1)
        ev_other = EventList(time=[40, 50, 60], dt = 3)
        with pytest.warns(UserWarning):
            ev_new = ev.join(ev_other)

        assert ev_new.dt == 3

    def test_join_without_energy(self):
        ev = EventList(time=[1, 2, 3], energy=[3, 3, 3])
        ev_other = EventList(time=[4, 5])
        ev_new = ev.join(ev_other)

        assert np.allclose(ev_new.energy, [3, 3, 3, 0, 0])

    def test_join_without_pi(self):
        ev = EventList(time=[1, 2, 3], pi=[3, 3, 3])
        ev_other = EventList(time=[4, 5])
        ev_new = ev.join(ev_other)

        assert np.allclose(ev_new.pi, [3, 3, 3, 0, 0])

    def test_join_with_gti_none(self):
        ev = EventList(time=[1, 2, 3])
        ev_other = EventList(time=[4, 5], gti=[[3.5, 5.5]])
        with warnings.catch_warnings(record=True):
            ev_new = ev.join(ev_other)

        assert np.allclose(ev_new.gti, [[1, 3], [3.5, 5.5]])

        ev = EventList(time=[1, 2, 3], gti=[[0.5, 3.5]])
        ev_other = EventList(time=[4, 5])
        with warnings.catch_warnings(record=True):
            ev_new = ev.join(ev_other)

        assert np.allclose(ev_new.gti, [[0.5, 3.5], [4, 5]])

        ev = EventList(time=[1, 2, 3])
        ev_other = EventList(time=[4, 5])
        with warnings.catch_warnings(record=True):
            ev_new = ev.join(ev_other)

        assert ev_new.gti == None

    def test_non_overlapping_join(self):
        """Join two overlapping event lists.
        """
        ev = EventList(time=[1, 1, 2, 3, 4],
                        energy=[3, 4, 7, 4, 3], gti=[[1, 2],[3, 4]])
        ev_other = EventList(time=[5, 6, 6, 7, 10],
                            energy=[4, 3, 8, 1, 2], gti=[[6, 7]])
        with pytest.warns(UserWarning) as record:
            ev_new = ev.join(ev_other)

        assert np.any(["GTIs in these" in r.message.args[0]
                       for r in record])

        assert (ev_new.time ==
                np.array([1, 1, 2, 3, 4, 5, 6, 6, 7, 10])).all()
        assert (ev_new.energy ==
                np.array([3, 4, 7, 4, 3, 4, 3, 8, 1, 2])).all()
        assert (ev_new.gti ==
                np.array([[1, 2],[3, 4],[6, 7]])).all()

    def test_overlapping_join(self):
        """Join two non-overlapping event lists.
        """
        ev = EventList(time=[1, 1, 10, 6, 5],
                        energy=[10, 6, 3, 11, 2], gti=[[1, 3],[5, 6]])
        ev_other = EventList(time=[5, 7, 6, 6, 10],
                            energy=[2, 3, 8, 1, 2], gti=[[5, 7],[8, 10]])
        ev_new = ev.join(ev_other)

        assert (ev_new.time ==
                np.array([1, 1, 5, 5, 6, 6, 6, 7, 10, 10])).all()
        assert (ev_new.energy ==
                np.array([10, 6, 2, 2, 11, 8, 1, 3, 3, 2])).all()
        assert (ev_new.gti == np.array([[5, 6]])).all()

    def test_overlapping_join_change_mjdref(self):
        """Join two non-overlapping event lists.
        """
        ev = EventList(time=[1, 1, 10, 6, 5],
                       energy=[10, 6, 3, 11, 2], gti=[[1, 3], [5, 6]],
                       mjdref=57001)
        ev_other = EventList(time=np.asarray([5, 7, 6, 6, 10]) + 86400,
                             energy=[2, 3, 8, 1, 2],
                             gti=np.asarray([[5, 7], [8, 10]]) + 86400,
                             mjdref=57000)
        ev_new = ev.join(ev_other)

        assert np.allclose(ev_new.time,
                           np.array([1, 1, 5, 5, 6, 6, 6, 7, 10, 10]))
        assert (ev_new.energy ==
                np.array([10, 6, 2, 2, 11, 8, 1, 3, 3, 2])).all()
        assert np.allclose(ev_new.gti, np.array([[5, 6]]))

    @pytest.mark.skipif('not (_HAS_YAML and _HAS_TIMESERIES)')
    def test_io_with_ascii(self):
        ev = EventList(self.time)
        ev.write('ascii_ev.ecsv', format_='ascii')
        ev = ev.read('ascii_ev.ecsv', format_='ascii')
        print(ev.time, self.time)
        assert np.allclose(ev.time, self.time)
        os.remove('ascii_ev.ecsv')

    def test_io_with_pickle(self):
        ev = EventList(self.time, mjdref=54000)
        ev.write('ev.pickle', format_='pickle')
        ev = ev.read('ev.pickle', format_='pickle')
        assert np.allclose(ev.time, self.time)
        os.remove('ev.pickle')

    @pytest.mark.skipif("not _H5PY_INSTALLED")
    def test_io_with_hdf5(self):
        ev = EventList(time=self.time, mjdref=54000)
        ev.write('ev.hdf5', format_='hdf5')

        ev = ev.read('ev.hdf5', format_='hdf5')
        assert np.allclose(ev.time, self.time)
        os.remove('ev.hdf5')

    def test_io_with_fits(self):
        ev = EventList(time=self.time, mjdref=54000)
        ev.write('ev.fits', format_='fits')
        ev = ev.read('ev.fits', format_='fits')
        assert np.allclose(ev.time, self.time)
        os.remove('ev.fits')

    def test_fits_with_standard_file(self):
        """Test that fits works with a standard event list
        file.
        """
        fname = os.path.join(datadir, 'monol_testA.evt')
        ev = EventList()
        ev = ev.read(fname, format_='hea')
        assert np.isclose(ev.mjdref, 55197.00076601852)

    def test_fits_with_additional(self):
        """Test that fits works with a standard event list
        file.
        """
        fname = os.path.join(datadir, 'xmm_test.fits')
        ev = EventList()
        ev = ev.read(fname, format_='hea', additional_columns=['PRIOR'])
        assert hasattr(ev, 'prior')

    @pytest.mark.skipif('not _HAS_TIMESERIES')
    def test_timeseries_roundtrip(self):
        """Test that io methods raise Key Error when
        wrong format is provided.
        """
        N = len(self.time)
        ev = EventList(time=self.time, gti=self.gti, energy=np.zeros(N),
                       pi=np.ones(N), mission="BUBU", instr="BABA",
                       mjdref=53467.)
        ts = ev.to_astropy_timeseries()
        new_ev = ev.from_astropy_timeseries(ts)
        for attr in ['time', 'energy', 'pi', 'gti']:
            assert np.allclose(getattr(ev, attr), getattr(new_ev, attr))
        for attr in ['mission', 'instr', 'mjdref']:
            assert getattr(ev, attr) == getattr(new_ev, attr)

    def test_table_roundtrip(self):
        """Test that io methods raise Key Error when
        wrong format is provided.
        """
        N = len(self.time)
        ev = EventList(time=self.time, gti=self.gti, energy=np.zeros(N),
                       pi=np.ones(N), mission="BUBU", instr="BABA",
                       mjdref=53467.)
        ts = ev.to_astropy_table()
        new_ev = ev.from_astropy_table(ts)
        for attr in ['time', 'energy', 'pi', 'gti']:
            assert np.allclose(getattr(ev, attr), getattr(new_ev, attr))
        for attr in ['mission', 'instr', 'mjdref']:
            assert getattr(ev, attr) == getattr(new_ev, attr)

