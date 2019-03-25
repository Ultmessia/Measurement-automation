from time import sleep

from lib2.VNATimeResolvedDispersiveMeasurement import *
import numpy as np
from qutip import *
from math import *
from matplotlib import pyplot as plt, colorbar

from scipy import optimize
from tqdm import tqdm_notebook



class Tomo:
    """
    Class for tomograhy
    Finds density matrix minimizing cost function for the measurements conducted.

    Requires either:
        - (one measurement operator + single qubit rotations) to be uploaded
        Methods:
            upload_rotation_sequence_from_command_list(...)
            upload_measurement_operator(...)
            construct_measurements(...)

        - (measurement operators + measured expected values) to be uploaded directly
        Methods:
            upload_measurements(...)
    Use find_rho() to get density matrix. Optimization procedure is launched several times and best result is shown.
    """

    def __init__(self, dim=4):
        self._dim = dim
        self._local_rotations = []
        self._measurement_operator = []
        self._measurements = []

    @staticmethod
    def x_to_rho(x):                                # Density matrix parametrization via Choletsky decomposition
        dim = int(sqrt(len(x)))
        t = np.identity(dim, complex)
        for i in range(dim):
            t[i, i] = abs(x[i])
        k = dim
        for i in range(dim):
            for l in range(i + 1, dim):
                t[i, l] = x[k] + 1j * x[k + 1]
                k += 2
        q_dim = [2] * int(log(dim) / log(2))
        rho = Qobj(t, dims=[q_dim, q_dim])
        rho = rho.dag() * rho
        rho = rho / rho.tr()
        return rho

    @staticmethod
    def rotator_from_command(com):
        """
        Constructs QObj from the string containing command
        Commands can start from '+' or '-' determining
        Axes goes next: 'I', 'X', 'Y' or 'Z'
        Commands also can contain '/' + number which refers to the length of the pulse
        Commands examples: '+X', '-Y/2', '-Z/6', '+I', ...
        """
        axes = {'I': identity(2), 'X': sigmax(), 'Y': sigmay(), 'Z': sigmaz()}
        ax = axes[com[1]]
        amp = eval(com[0] + '1' + com[2:])
        return (-1j * amp * pi / 2 * ax).expm()

    def upload_rotation_sequence_from_command_list(self, com_list):
        rot_seq = []
        for coms in com_list:
            op = tensor(list(map(self.rotator_from_command, coms)))
            rot_seq.append(op)
        self._local_rotations = rot_seq

    def upload_measurement_operator(self, meas_op):
        self._measurement_operator = meas_op

    def construct_measurements(self, measurement_results):
        """
        Construct measurement sequence required for reconstruction
        Tomo.upload_rotation_sequence_from_command_list() and Tomo.upload_measurement_operator must be uploaded
        :param measurement_results: measured expected values
        """
        self._measurements = [(rot.dag() * self._measurement_operator * rot, res)
                                for (rot, res) in zip(self._local_rotations, measurement_results)]

    def construct_measurements_from_matrix(self, dens_matrix):
        """
        Construct measurement sequence required for reconstruction
        Tomo.upload_rotation_sequence_from_command_list() and Tomo.upload_measurement_operator must be uploaded
        :param dens_matrix: density matrix to construct measurement outcomes
        """
        self._measurements = [(rot.dag() * self._measurement_operator * rot,
                               expect(dens_matrix, rot.dag() * self._measurement_operator * rot))
                              for rot in self._local_rotations]

    def upload_measurements(self, meas):            # Загрузить набор измерений [(оператор, измеренное. среднее), ...]
        """
        Measurement sequence can be uploaded manually
        Format: [(measurement operator, measured expected value), ...]
        """
        self._measurements = meas

    def likelihood(self, x):                        # Вычисление Likelihood по загруженным измерениям \
        rho = self.x_to_rho(x)                      # для матрицы плотности заданной через x
        lh = 0
        for (op, ex) in self._measurements:
            lh += (expect(rho, op) - ex) ** 2
        return lh

    def find_rho(self, average=5):  # Минимизации Likelihood
        for n in tqdm_notebook(range(average), desc='Tomography: Likelihood minimization', ncols=700):
            x0 = np.random.rand(self._dim ** 2) * 2 - 1
            new = optimize.minimize(self.likelihood, x0, method='L-BFGS-B')
            if n == 0:
                best = new
            else:
                if new.fun < best.fun:
                    best = new
        return self.x_to_rho(best.x)


class DispersiveJointTomography(VNATimeResolvedDispersiveMeasurement):

    def __init__(self, name, sample_name, **devs_aliases_map):
        super().__init__(name, sample_name, devs_aliases_map)
        self._measurement_result = \
            DispersiveJointTomographyResult(name, sample_name)
        self._sequence_generator = IQPulseBuilder.build_joint_tomography_pulse_sequences

    def set_fixed_parameters(self, pulse_sequence_parameters, betas,
                             detect_resonator=True, plot_resonator_fit=True,
                             **dev_params):
        super().set_fixed_parameters(pulse_sequence_parameters, **dev_params)
        self._measurement_result.upload_betas(*betas)

    def set_swept_parameters(self, local_rotations_list):
        """
        :param local_rotations_list: should have form:
                    { (q1_rot_1, q2_rot_1),
                      (q1_rot_2, q2_rot_2),
                      ...
                    }
            e.g.    { ('+X/2', '-Y'),
                      ('+X', '+X')
                    }
        """
        swept_pars = {"tomo_local_rotations":
                          (self._set_tomo_params, local_rotations_list)}
        super().set_swept_parameters(**swept_pars)
        self._measurement_result.upload_local_rotations(local_rotations_list)

    def _set_tomo_params(self, local_rotations):
        self._pulse_sequence_parameters["tomo_local_rotations"] = local_rotations
        super()._output_pulse_sequence()

    # TODO
    #     1. Preparation pulse sequence
    #     2. Rotation pulses on both qubits
    #     3. set_swept_parameters -- Any changes required?
    #           Change to
        '''
        swept_pars :{'par1': [value1, value2, ...],
                     'par2': [value1, value2, ...], ...,
                     'setter' : setter}
        '''
    #            Instead of
        '''
        swept_pars :{'par1': (setter1, [value1, value2, ...]),
                     'par2': (setter2, [value1, value2, ...]), ...}
        '''


class DispersiveJointTomographyResult(VNATimeResolvedDispersiveMeasurementResult):      # TODO

    def __init__(self, name, sample_name):
        super().__init__(name, sample_name)
        self._local_rotations_list = []
        self._pulse_sequence_parameters = self._context \
            .get_pulse_sequence_parameters()
        self._betas = (0, 0, 0, 0)

    def upload_local_rotations(self, local_rotations_list):
        self._local_rotations_list = local_rotations_list

    def upload_betas(self, *betas):
        self._betas = betas

    def find_density_matrix(self):
        beta_II, beta_ZI, beta_IZ, beta_ZZ = self._betas
        joint_op = (beta_II * tensor(identity(2), identity(2)) +
                    beta_ZI * tensor(sigmaz(), identity(2)) +
                    beta_IZ * tensor(identity(2), sigmaz()) +
                    beta_ZZ * tensor(sigmaz(), sigmaz()))

        tomo = Tomo(dim=4)
        tomo.upload_measurement_operator(joint_op)
        tomo.upload_rotation_sequence_from_command_list(self._local_rotations_list)

        res = self.get_data()['data']
        tomo.construct_measurements(res)
        return tomo.find_rho()

    def find_density_matrix_sim(self, dens_matrix):
        """
        For simulations:
            Constructs measurement outcomes based on the matrix given
        :param dens_matrix: density matrix to construct measurement outcomes
        """
        beta_II, beta_ZI, beta_IZ, beta_ZZ = self._betas
        joint_op = (beta_II * tensor(identity(2), identity(2)) +
                    beta_ZI * tensor(sigmaz(), identity(2)) +
                    beta_IZ * tensor(identity(2), sigmaz()) +
                    beta_ZZ * tensor(sigmaz(), sigmaz()))

        self._tomo = Tomo(dim=4)
        self._tomo.upload_measurement_operator(joint_op)
        self._tomo.upload_rotation_sequence_from_command_list(self._local_rotations_list)

        self._tomo.construct_measurements_from_matrix(dens_matrix)
        return self._tomo.find_rho()

    def _prepare_figure(self):
        fig, axes = plt.subplots(1, 2, figsize=(15, 7), sharex=True)
        fig.canvas.set_window_title(self._name)
        axes = ravel(axes)
        for ax in axes:
            ax.set_xlabel('Qubit 2 local rotations')
            ax.set_ylabel('Qubit 1 local rotations')
        cax_amps, kw = colorbar.make_axes(axes[0], aspect=40)
        cax_phas, kw = colorbar.make_axes(axes[1], aspect=40)
        cax_amps.set_title("$|S_{21}|$", position=(0.5, -0.05))
        cax_phas.set_title("$\\angle S_{21}$\n [%s]" % self._phase_units,
                           position=(0.5, -0.1))
        return fig, axes, (cax_amps, cax_phas)

    def _plot(self, data):
        axes = self._axes
        caxes = self._caxes
        if "data" not in data.keys():
            return

        keys1 = [x[0] for x in data['tomo_local_rotations']]
        keys2 = [x[1] for x in data['tomo_local_rotations']]
        data_dict = dict.fromkeys(keys1)
        for key in data_dict.keys():
            data_dict[key] = dict.fromkeys(keys2)
        keys1 = list(data_dict.keys())
        keys2 = list(data_dict[keys1[0]].keys())
        list(zip(data['tomo_local_rotations'], data['data']))
        for ((rot1, rot2), res) in zip(data['tomo_local_rotations'], data['data']):
            data_dict[rot1][rot2] = res

        data_matrix = [[data_dict[k1][k2] if data_dict[k1][k2] is not None else 0
                        for k2 in keys2] for k1 in keys1]
        plots = axes[0].imshow(abs(data_matrix)), axes[1].imshow(angle(data_matrix))
        plt.colorbar(plots[0], cax=caxes[0])
        plt.colorbar(plots[1], cax=caxes[1])
        # axes[0].set_title('Real')
        # axes[1].set_title('Imag')
        for (ax, cax) in zip(axes, caxes):
            ax.set_xticks(range(len(keys2)))
            ax.set_yticks(range(len(keys1)))
            ax.set_xticklabels(keys2)
            ax.set_yticklabels(keys1)
            for i in range(len(keys1)):
                for j in range(len(keys2)):
                    if data_dict[keys1[i]][keys2[j]] is None:
                        ax.text(j, i, 'No data', ha="center", va="center", color="w")
