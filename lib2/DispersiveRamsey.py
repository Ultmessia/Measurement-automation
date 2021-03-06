
from lib2.VNATimeResolvedDispersiveMeasurement1D import *

class DispersiveRamsey(VNATimeResolvedDispersiveMeasurement1D):

    def __init__(self, name, sample_name,line_attenuation_db = 60, plot_update_interval=1,
     **devs_aliases_map):
        devs_aliases_map["q_z_awg"] = None
        super().__init__(name, sample_name, devs_aliases_map, line_attenuation_db,
         plot_update_interval)
        self._measurement_result = DispersiveRamseyResult(name,
                    sample_name)
        self._sequence_generator = IQPulseBuilder.build_dispersive_ramsey_sequences
        self._swept_parameter_name = "ramsey_delay"

    def set_swept_parameters(self, ramsey_delays):
        super().set_swept_parameters(self._swept_parameter_name, ramsey_delays)


class DispersiveRamseyResult(VNATimeResolvedDispersiveMeasurement1DResult):

    def _model(self, t, A_r, A_i, T_2_ast, Delta_Omega, offset_r,
        offset_i, phase):
        return (A_r+1j*A_i)*exp(-1/T_2_ast*t)*cos(Delta_Omega*t+phase)\
                                                    +offset_r+1j*offset_i

    def _generate_fit_arguments(self, x, data):
        time_step = x[1]-x[0]
        max_frequency = 1/time_step/2/3
        frequency = random.random(1)*max_frequency
        phase = random.random(1)*2*pi-pi

        bounds =([-10, -10, 0.1, 0*2*pi, -10, -10, -pi],
                        [10, 10, 100, max_frequency*2*pi, 10, 10, pi])
        amp_r, amp_i = ptp(real(data))/2, ptp(imag(data))/2
        p0 = (amp_r, amp_i, 3, frequency, max(real(data))-amp_r,
                                max(imag(data))-amp_i, 0)
        return p0, bounds

    def get_ramsey_frequency(self):
        return self._fit_params[3]/2/pi*1e6

    def _generate_annotation_string(self, opt_params, err):
        return "$T_2^*=%.2f \pm %.2f \mu$s\n$|\Delta\omega/2\pi| = %.3f \pm %.3f$ MHz"%\
            (opt_params[2], err[2], opt_params[3]/2/pi, err[3]/2/pi)
