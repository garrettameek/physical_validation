###########################################################################
#                                                                         #
#    physical_validation,                                                 #
#    a python package to test the physical validity of MD results         #
#                                                                         #
#    Written by Michael R. Shirts <michael.shirts@colorado.edu>           #
#               Pascal T. Merz <pascal.merz@colorado.edu>                 #
#                                                                         #
#    Copyright (C) 2012 University of Virginia                            #
#              (C) 2017 University of Colorado Boulder                    #
#                                                                         #
#    This library is free software; you can redistribute it and/or        #
#    modify it under the terms of the GNU Lesser General Public           #
#    License as published by the Free Software Foundation; either         #
#    version 2.1 of the License, or (at your option) any later version.   #
#                                                                         #
#    This library is distributed in the hope that it will be useful,      #
#    but WITHOUT ANY WARRANTY; without even the implied warranty of       #
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU    #
#    Lesser General Public License for more details.                      #
#                                                                         #
#    You should have received a copy of the GNU Lesser General Public     #
#    License along with this library; if not, write to the                #
#    Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor,     #
#    Boston, MA 02110-1301 USA                                            #
#                                                                         #
###########################################################################
r"""
This software allows users to perform statistical test to determine if a 
given molecular simulation is consistent with the thermodynamic ensemble 
it is performed in.

Users should cite the JCTC paper: Shirts, "M. R. Simple Quantitative 
Tests to Validate Sampling from Thermodynamic Ensembles", 
J. Chem. Theory Comput., 2013, 9 (2), pp 909–926, 
http://dx.doi.org/10.1021/ct300688p

"""

import numpy as np

from physical_validation.util import timeseries
from physical_validation.util import checkensemble
from physical_validation.data import simulation_data
import physical_validation.util.error as pv_error


def check(data_sim_one, data_sim_two,
          total_energy=False,
          screen=False, filename=None):
    r"""
    Check the ensemble. The correct check is inferred from the
    simulation data given.
    
    Parameters
    ----------
    data_sim_one : SimulationData
    data_sim_two : SimulationData
    total_energy : bool

    Returns
    -------

    """
    if not simulation_data.SimulationData.compatible(data_sim_one,
                                                     data_sim_two):
        raise pv_error.InputError(['data_sim_one', 'data_sim_two'],
                                  'Simulation data not compatible.')

    if data_sim_one.ensemble.ensemble != data_sim_two.ensemble.ensemble:
        raise pv_error.InputError(['data_sim_one', 'data_sim_two'],
                                  'The two simulations were sampling different ensembles. '
                                  'The simulations are expected to differ in state point '
                                  '(e.g. target temperature, target pressure), but not '
                                  'in their sampled ensemble (e.g. NVT, NPT).')

    ensemble = data_sim_one.ensemble.ensemble

    if ensemble == 'NVE' or ensemble == 'muVE':
        raise pv_error.InputError(['data_sim_one', 'data_sim_two'],
                                  'Test of ensemble ' + ensemble + ' is not implemented '
                                  '(yet).')

    n1 = data_sim_one.observables.nframes
    n2 = data_sim_two.observables.nframes

    if total_energy:
        e1 = data_sim_one.observables.total_energy
        e2 = data_sim_two.observables.total_energy
    else:
        e1 = data_sim_one.observables.potential_energy
        e2 = data_sim_two.observables.potential_energy

    # padding the array - checkensemble requires same length
    if n1 < n2:
        e1 = np.append(e1, np.zeros(n2-n1))
    if n2 < n1:
        e2 = np.append(e2, np.zeros(n1-n2))

    number_of_samples = np.array([n1, n2])
    energy = np.array([e1, e2])

    do_linear_fit = True
    do_non_linear_fit = False
    do_max_likelhood = True
    do_maxwell = False

    if ensemble == 'NVT':
        temperatures = np.array([data_sim_one.ensemble.temperature,
                                 data_sim_two.ensemble.temperature])

        analysis_type = 'dbeta-constV'

        ge = []
        for e in energy:
            ge.append(timeseries.statisticalInefficiency(e, fast=False))

        checkensemble.ProbabilityAnalysis(number_of_samples, type=analysis_type,
                                          T_k=temperatures, P_k=None, mu_k=None,
                                          U_kn=energy, V_kn=None, N_kn=None,
                                          nbins=40, reptype='bootstrap', g=ge,
                                          nboots=200, bMaxwell=do_maxwell, bLinearFit=do_linear_fit,
                                          bNonLinearFit=do_non_linear_fit, bMaxLikelihood=do_max_likelhood, seed=123456,
                                          kB=data_sim_one.units.kb, eunits=data_sim_one.units.energy,
                                          vunits=data_sim_one.units.volume, punits=data_sim_one.units.pressure,
                                          filename=filename, screen=screen)

    elif ensemble == 'NPT':
        temperatures = np.array([data_sim_one.ensembles.temperature,
                                 data_sim_two.ensembles.temperature])
        pressures = np.array([data_sim_one.ensembles.pressure,
                              data_sim_two.ensembles.pressure])
        equal_temps = temperatures[0] == temperatures[1]
        equal_press = pressures[0] == pressures[1]

        v1 = data_sim_one.observable.volume
        v2 = data_sim_two.observable.volume
        # padding the array - checkensemble requires same length
        if n1 < n2:
            v1 = np.append(v1, np.zeros(n2-n1))
        if n2 < n1:
            v2 = np.append(v2, np.zeros(n1-n2))
        volume = np.array([v1, v2])

        if equal_press and not equal_temps:
            analysis_type = 'dbeta-constP'
        elif equal_temps and not equal_press:
            analysis_type = 'dpressure-constB'
        else:
            analysis_type = 'dbeta-dpressure'
            do_linear_fit = False
            do_non_linear_fit = False

        ge = []
        for e in energy:
            ge.append(timeseries.statisticalInefficiency(e, fast=False))
        gv = []
        for v in volume:
            gv.append(timeseries.statisticalInefficiency(v, fast=False))
        g = np.maximum(ge, gv)

        checkensemble.ProbabilityAnalysis(number_of_samples, type=analysis_type,
                                          T_k=temperatures, P_k=None, mu_k=None,
                                          U_kn=energy, V_kn=None, N_kn=None,
                                          kB=data_sim_one.units.kb, nbins=40,
                                          bMaxLikelihood=do_max_likelhood, bLinearFit=do_linear_fit,
                                          bNonLinearFit=do_non_linear_fit, reptype='bootstrap', nboots=200,
                                          g=g,
                                          bMaxwell=do_maxwell,
                                          eunits=data_sim_one.units.energy, vunits=data_sim_one.units.volume,
                                          punits=data_sim_one.units.pressure, seed=123456,
                                          screen=screen, filename=filename)