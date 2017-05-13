from lib2.Measurement import *
from lib2.MeasurementResult import *
from lib2.IQPulseSequence import *

from scipy.optimize import curve_fit

class VNATimeResolvedDispersiveMeasurementContext(ContextBase):

    def __init__(self, equipment = {}, pulse_sequence_parameters = {}, comment = ""):
        '''
        Parameters:
        -----------
        equipment: dict
            a dict containing dicts representing device parameters
        pulse_sequence_parameters: dict
            should contain all control parameters of the pulse sequence used in
            the measurement
        '''
        super().__init__(equipment, comment)
        self._pulse_sequence_parameters = pulse_sequence_parameters

    def get_pulse_sequence_parameters(self):
        return self._pulse_sequence_parameters

    def to_string(self):
        return "Pulse sequence parameters:\n"+str(self._pulse_sequence_parameters)+\
            super().to_string()


class VNATimeResolvedDispersiveMeasurement(Measurement):

    def __init__(self, name, sample_name, vna_name, ro_awg_name, q_awg_name,
        q_lo_name, line_attenuation_db = 60, plot_update_interval = 1):
        super().__init__(name, sample_name, devs_names=[vna_name, ro_awg_name,
            q_awg_name, q_lo_name], plot_update_interval=plot_update_interval)

        self._ro_awg = self._actual_devices[ro_awg_name]
        self._q_awg = self._actual_devices[q_awg_name]
        self._vna = self._actual_devices[vna_name]
        self._q_lo = self._actual_devices[q_lo_name]

    def set_fixed_parameters(self, vna_parameters, q_lo_parameters,
        ro_awg_parameters, q_awg_parameters, pulse_sequence_parameters):

        self._pulse_sequence_parameters = pulse_sequence_parameters
        self._measurement_result.get_context()\
                .get_pulse_sequence_parameters()\
                .update(pulse_sequence_parameters)

        res_freq = self._detect_resonator(vna_parameters)
        vna_parameters["freq_limits"] = (res_freq, res_freq)

        super().set_fixed_parameters(vna=vna_parameters, q_lo=q_lo_parameters,
                            ro_awg=ro_awg_parameters, q_awg=q_awg_parameters)

    def _recording_iteration(self):
        vna = self._vna
        vna.avg_clear(); vna.prepare_for_stb();
        vna.sweep_single(); vna.wait_for_stb();
        return mean(vna.get_sdata())

    def _detect_resonator(self, vna_parameters):
        self._q_lo.set_output_state("OFF")
        print("Detecting a resonator within provided frequency range of the VNA %s\
                    "%(str(vna_parameters["freq_limits"])))
        self._vna.set_nop(200)
        self._vna.set_freq_limits(*vna_parameters["freq_limits"])
        self._vna.set_power(vna_parameters["power"])
        self._vna.set_bandwidth(vna_parameters["bandwidth"]*10)
        self._vna.set_averages(vna_parameters["averages"])
        res_freq, res_amp, res_phase = super()._detect_resonator()
        print("Detected frequency is %.5f GHz, at %.2f mU and %.2f degrees"%\
                    (res_freq/1e9, res_amp*1e3, res_phase/pi*180))
        self._q_lo.set_output_state("ON")
        return res_freq

    def _output_rabi_sequence(self, excitation_duration):
        awg_trigger_reaction_delay = \
                self._pulse_sequence_parameters["awg_trigger_reaction_delay"]
        readout_duration = \
                self._pulse_sequence_parameters["readout_duration"]
        repetition_period = \
                self._pulse_sequence_parameters["repetition_period"]

        q_pb = self._q_awg.get_pulse_builder()
        q_pb.add_zero_pulse(awg_trigger_reaction_delay)\
            .add_sine_pulse(excitation_duration, 0)\
            .add_zero_pulse(readout_duration)\
            .add_zero_until(repetition_period)
        self._q_awg.output_pulse_sequence(q_pb.build())

        ro_pb = self._ro_awg.get_pulse_builder()
        ro_pb.add_zero_pulse(excitation_duration)\
             .add_dc_pulse(readout_duration)\
             .add_zero_pulse(100)
        self._ro_awg.output_pulse_sequence(ro_pb.build())

    def _output_ramsey_sequence(self, ramsey_delay):
        awg_trigger_reaction_delay = \
                self._pulse_sequence_parameters["awg_trigger_reaction_delay"]
        readout_duration = \
                self._pulse_sequence_parameters["readout_duration"]
        repetition_period = \
                self._pulse_sequence_parameters["repetition_period"]
        half_pi_pulse_duration = \
                self._pulse_sequence_parameters["half_pi_pulse_duration"]

        q_pb = self._q_awg.get_pulse_builder()
        q_pb.add_zero_pulse(awg_trigger_reaction_delay)\
            .add_sine_pulse(half_pi_pulse_duration, 0)\
            .add_zero_pulse(ramsey_delay)\
            .add_sine_pulse(half_pi_pulse_duration,
                    time_offset = half_pi_pulse_duration+ramsey_delay)\
            .add_zero_pulse(readout_duration)\
            .add_zero_until(repetition_period)
        self._q_awg.output_pulse_sequence(q_pb.build())

        ro_pb = self._ro_awg.get_pulse_builder()
        ro_pb.add_zero_pulse(2*half_pi_pulse_duration+ramsey_delay)\
             .add_dc_pulse(readout_duration)\
             .add_zero_pulse(100)
        self._ro_awg.output_pulse_sequence(ro_pb.build())

class VNATimeResolvedDispersiveMeasurementResult(MeasurementResult):

    def __init__(self, name, sample_name):
        super().__init__(name, sample_name)
        self._context = VNATimeResolvedDispersiveMeasurementContext()
        self._is_finished = False
        self._phase_units = "rad"
        self._data_formats = {
            "abs":(abs, "Transmission amplitude [a.u.]"),
            "real":(real,"Transmission real part [a.u.]"),
            "phase":(angle, "Transmission phase [%s]"%self._phase_units),
            "imag":(imag, "Transmission imaginary part [a.u.]")}

    def _prepare_figure(self):
        fig, axes = plt.subplots(2, 2, figsize=(15,7), sharex=True)
        axes = ravel(axes)
        return fig, axes, (None, None)